# -*- coding: utf-8 -*-
"""German_traffic_PyTorch.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1FC0V5Jk3eXeLksRQBsGfzT1Kyc8PO65R
"""

# Jovian Commit Essentials
# Please retain and execute this cell without modifying the contents for `jovian.commit` to work
!pip install jovian --upgrade -q
import jovian
jovian.utils.colab.set_colab_file_id('1FC0V5Jk3eXeLksRQBsGfzT1Kyc8PO65R')

!pip install jovian --upgrade --quiet
! install opendatasets --upgrade --pipquiet

# Commented out IPython magic to ensure Python compatibility.
import opendatasets as od
import os
import torch
import torchvision
import torch.nn as nn
import torch.nn.functional as F
from torchvision.datasets import ImageFolder
from torch.utils.data import DataLoader
import torchvision.transforms as T
from torch.utils.data import random_split
import torch.utils.data as data
from torchvision.utils import make_grid
import torch.optim as optim

import matplotlib
import matplotlib.pyplot as plt
# %matplotlib inline

matplotlib.rcParams['figure.facecolor'] = '#ffffff'

dataset_url="https://www.kaggle.com/meowmeowmeowmeowmeow/gtsrb-german-traffic-sign"
od.download(dataset_url)

input_data="/content/gtsrb-german-traffic-sign/Train"
c1=os.listdir(input_data)
print(c1)

train_dataset="/content/gtsrb-german-traffic-sign/Train"
classes=os.listdir(train_dataset)
print(classes)

data_transforms =torchvision.transforms.Compose([
    T.Resize([32,32]),
    #T.CenterCrop(32),
    #T.ColorJitter(brightness=0.5, contrast=0.1, saturation=0.1, hue=0.1),
    T.transforms.ToTensor()
    ])

train_data_path ="/content/gtsrb-german-traffic-sign/train"
train_dataset = torchvision.datasets.ImageFolder(root = train_data_path, transform = data_transforms)

"""# Data Split for Training

"""

val_len=5000
train_len=len(train_dataset)-val_len
train_data,val_data=data.random_split(train_dataset,[train_len,val_len])

len(train_data)

BATCH_SIZE = 32
learning_rate = 0.001
EPOCHS = 15
numClasses = 43

train_loader = data.DataLoader(train_data, shuffle=True, batch_size = BATCH_SIZE,num_workers=3,pin_memory=True)
val_loader = data.DataLoader(val_data,batch_size = BATCH_SIZE*2,num_workers=3,pin_memory=True)

"""# Helper Functions

##For Visualisation
"""

def show_batch(dl):
    for images, labels in dl:
        fig, ax = plt.subplots(figsize=(12,12))
        ax.set_xticks([]); ax.set_yticks([])
        ax.imshow(make_grid(images[:64], nrow=8).permute(1, 2, 0).clamp(0,1))
        break

show_batch(train_loader)

import jovian

project_name="01-German_traffic"
jovian.commit(project=project_name)

"""## For GPU"""

def get_default_device():
    """Pick GPU if available, else CPU"""
    if torch.cuda.is_available():
        return torch.device('cuda')
    else:
        return torch.device('cpu')
    
def to_device(data, device):
    """Move tensor(s) to chosen device"""
    if isinstance(data, (list,tuple)):
        return [to_device(x, device) for x in data]
    return data.to(device, non_blocking=True)

class DeviceDataLoader():
    """Wrap a dataloader to move data to a device"""
    def __init__(self, dl, device):
        self.dl = dl
        self.device = device
        
    def __iter__(self):
        """Yield a batch of data after moving it to device"""
        for b in self.dl: 
            yield to_device(b, self.device)

    def __len__(self):
        """Number of batches"""
        return len(self.dl)

device = get_default_device()
device

train_dl = DeviceDataLoader(train_loader, device)
valid_dl = DeviceDataLoader(val_loader, device)

"""## For Accuracy"""

def accuracy(outputs, labels):
    _, preds = torch.max(outputs, dim=1)
    return torch.tensor(torch.sum(preds == labels).item() / len(preds))

"""#Model Class

Loss and Propagation
"""

# Define optimizer and criterion functions
optimizer = optim.Adam(model.parameters(), lr=learning_rate)
criterion = nn.CrossEntropyLoss()

class ImageBase(nn.Module):
    def training_step(self, batch):
        images, labels = batch 
        out = self(images)                  # Generate predictions
        loss = F.cross_entropy(out, labels) # Calculate loss
        return loss
    
    def validation_step(self, batch):
        images, labels = batch 
        out = self(images)                    # Generate predictions
        loss = F.cross_entropy(out, labels)   # Calculate loss
        acc = accuracy(out, labels)           # Calculate accuracy
        return {'val_loss': loss.detach(), 'val_acc': acc}
        
    def validation_epoch_end(self, outputs):
        batch_losses = [x['val_loss'] for x in outputs]
        epoch_loss = torch.stack(batch_losses).mean()   # Combine losses
        batch_accs = [x['val_acc'] for x in outputs]
        epoch_acc = torch.stack(batch_accs).mean()      # Combine accuracies
        return {'val_loss': epoch_loss.item(), 'val_acc': epoch_acc.item()}
    
    def epoch_end(self, epoch, result):
        print("Epoch [{}], last_lr: {:.5f}, train_loss: {:.4f}, val_loss: {:.4f}, val_acc: {:.4f}".format(
            epoch, result['lrs'][-1], result['train_loss'], result['val_loss'], result['val_acc']))

class Resnet(ImageBase):
    def __init__(self,in_channels, output_dim):
        super().__init__()
        
        self.features = nn.Sequential(
            nn.Conv2d(in_channels, out_channels=16, kernel_size=3, stride=1, padding=1),
            nn.Conv2d(in_channels=16, out_channels=32, kernel_size=3, stride=1, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2),  #32x16x16
            
            nn.Dropout(0.25),
            nn.Conv2d(in_channels=32, out_channels=64, kernel_size=3, stride=1, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_channels=64, out_channels=128, kernel_size=3, stride=1, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2),  #128x8x8
            
            nn.Dropout(0.25)
            #nn.Flatten()
            )
        
        self.classifier = nn.Sequential(
            nn.Linear(128*8*8, 512),
            nn.ReLU(inplace=True),
            
            nn.Dropout(0.5),
            nn.Linear(in_features=512, out_features=output_dim)
            )
        
    def forward(self, x):
        x = self.features(x)
        x = x.view(x.shape[0], -1)
        x = self.classifier(x)
        return x

model = Resnet(3,numClasses)
model = to_device(model, device)
# Function to count the number of parameters in the model
def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
# Print model
print(model)

# Print number of trainable parameters in the model
print(f'The model has {count_parameters(model):,} trainable parameters')

@torch.no_grad()
def evaluate(model, val_loader):
    model.eval()
    outputs = [model.validation_step(batch) for batch in val_loader]
    return model.validation_epoch_end(outputs)

def get_lr(optimizer):
    for param_group in optimizer.param_groups:
        return param_group['lr']

def fit_one_cycle(epochs, max_lr, model, train_loader, val_loader, 
                  weight_decay=0, grad_clip=None, opt_func=torch.optim.SGD):
    torch.cuda.empty_cache()
    history = []
    
    # Set up cutom optimizer with weight decay
    optimizer = opt_func(model.parameters(), max_lr, weight_decay=weight_decay)
    # Set up one-cycle learning rate scheduler
    sched = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr, epochs=epochs, 
                                                steps_per_epoch=len(train_loader))
    
    for epoch in range(epochs):
        # Training Phase 
        model.train()
        train_losses = []
        lrs = []
        for batch in train_loader:
            loss = model.training_step(batch)
            train_losses.append(loss)
            loss.backward()
            
            # Gradient clipping
            if grad_clip: 
                nn.utils.clip_grad_value_(model.parameters(), grad_clip)
            
            optimizer.step()
            optimizer.zero_grad()
            
            # Record & update learning rate
            lrs.append(get_lr(optimizer))
            sched.step()
        
        # Validation phase
        result = evaluate(model, val_loader)
        result['train_loss'] = torch.stack(train_losses).mean().item()
        result['lrs'] = lrs
        model.epoch_end(epoch, result)
        history.append(result)
    return history

history = [evaluate(model, valid_dl)]
history

epochs = 10
max_lr = 0.001
grad_clip = 0.1
weight_decay = 1e-6
opt_func = torch.optim.Adam

# Commented out IPython magic to ensure Python compatibility.
# %%time
# 
# history += fit_one_cycle(epochs, max_lr, model, train_dl, valid_dl, 
#                              grad_clip=grad_clip, 
#                              weight_decay=weight_decay, 
#                              opt_func=opt_func)

def plot_accuracies(history):
    accuracies = [x['val_acc'] for x in history]
    plt.plot(accuracies, '-x')
    plt.xlabel('epoch')
    plt.ylabel('accuracy')
    plt.title('Accuracy vs. No. of epochs');

plot_accuracies(history)

def plot_losses(history):
    train_losses = [x.get('train_loss') for x in history]
    val_losses = [x['val_loss'] for x in history]
    plt.plot(train_losses, '-bx')
    plt.plot(val_losses, '-rx')
    plt.xlabel('epoch')
    plt.ylabel('loss')
    plt.legend(['Training', 'Validation'])
    plt.title('Loss vs. No. of epochs');

plot_losses(history)

data_dir="/content/gtsrb-german-traffic-sign/Test"
test_class=os.listdir(data_dir)
test_class
#importing test dataset
import pandas as pd
dataset=pd.read_csv("/content/gtsrb-german-traffic-sign/Test.csv")
y_test=dataset['Path'].values
labels=dataset['ClassId'].values

y_test

truelabel = torch.tensor(labels)
truelabel

from PIL import Image
data=[]
path = "/content/gtsrb-german-traffic-sign/"
#print(path)
Class=os.listdir(path)
for a in y_test:
    img = Image.open(path+a)
    data_array=T.ToTensor()
    data_shape=data_array(img)
    img_PIL = T.ToPILImage()(data_shape)
    img_PIL = T.Resize([32,32])(img_PIL)
    img_PIL = T.ToTensor()(img_PIL)
    data.append(img_PIL)

print(len(data))
img_PIL.size()

test_dataset = []
for i in range(len(data)):
  test_dataset.append([data[i],truelabel[i]])

def predict_image(img, model):
    # Convert to a batch of 1
    xb = to_device(img.unsqueeze(0), device)
    # Get predictions from model
    yb = model(xb)
    #print(yb)
    ybNew=nn.Softmax(dim=1)
    ybNew= ybNew(yb)
    #print(ybNew)
    # Pick index with highest probability
    _, preds  = torch.max(ybNew, dim=1)
    #print(preds.item())
    # Retrieve the class label
    return preds.item()

len(data), type(img)

#from sklearn.metrics import accuracy_score
#print(accuracy_score(labels, predsTest))

test_acc

jovian.reset()
jovian.log_hyperparams({
    'num_epochs': epochs,
    'opt_func': opt_func.__name__,
    'batch_size': 32,
    'lr': max_lr,
})

jovian.log_metrics(val_loss=0.0083, 
                   val_acc=0.9980)

project_name="01-German_traffic"
jovian.commit(project=project_name, environment='None')

