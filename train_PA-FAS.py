import sys
sys.path.append('../../')

from utils.utils import save_checkpoint, AverageMeter, Logger, accuracy,accuracy_net2, mkdirs, time_to_str
from utils.evaluate import eval
from utils.dataset import get_dataset
from fas import fas_model_weighting2
import random
import numpy as np
from config import configC, configM, configI, configO, config_cefa, config_surf, config_wmca
from datetime import datetime
import time
from timeit import default_timer as timer

import os
import torch
import torch.nn as nn
import torch.optim as optim
import argparse
import matplotlib.pyplot as plt

rate = 95
patch = 0.21
pixel = 0.79
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
os.environ["CUDA_VISIBLE_DEVICES"] = '0'

def set_seed(args):
    """
    :param args:
    :return:
    """
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)
    torch.backends.cudnn.deterministic = True

def train(config):
  src1_train_dataloader_fake, src1_train_dataloader_real, src2_train_dataloader_fake, src2_train_dataloader_real, src3_train_dataloader_fake, src3_train_dataloader_real, src4_train_dataloader_fake, src4_train_dataloader_real, src5_train_dataloader_fake, src5_train_dataloader_real, test_dataloader = get_dataset(
      config.src1_data, config.src1_train_num_frames, config.src2_data,
      config.src2_train_num_frames, config.src3_data,
      config.src3_train_num_frames, config.src4_data,
      config.src4_train_num_frames, config.src5_data,
      config.src5_train_num_frames, config.tgt_data, config.tgt_test_num_frames)

  best_model_ACC = 0.0
  best_model_HTER = 1.0
  best_model_ACER = 1.0
  best_model_AUC = 0.0
  # 0:loss, 1:top-1, 2:EER, 3:HTER, 4:ACER, 5:AUC, 6:threshold
  valid_args = [np.inf, 0, 0, 0, 0, 0, 0, 0]

  loss_classifier = AverageMeter()
  classifer_top1 = AverageMeter()

  log = Logger()
  log.write(
      '\n----------------------------------------------- [START %s] %s\n\n' %
      (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), '-' * 51))
  log.write('** start training target model! **\n')
  log.write(
      '--------|------------- VALID -------------|--- classifier ---|------ Current Best ------|--------------|\n'
  )
  log.write(
      '  iter  |   loss   top-1   HTER    AUC    |   loss   top-1   |   top-1   HTER    AUC    |    time      |\n'
  )
  log.write(
      '-------------------------------------------------------------------------------------------------------|\n'
  )
  start = timer()
  criterion = {'softmax': nn.CrossEntropyLoss().cuda()}

 
  src1_train_iter_real = iter(src1_train_dataloader_real)
  src1_iter_per_epoch_real = len(src1_train_iter_real)
  src2_train_iter_real = iter(src2_train_dataloader_real)
  src2_iter_per_epoch_real = len(src2_train_iter_real)
  src3_train_iter_real = iter(src3_train_dataloader_real)
  src3_iter_per_epoch_real = len(src3_train_iter_real)
  src4_train_iter_real = iter(src4_train_dataloader_real)
  src4_iter_per_epoch_real = len(src4_train_iter_real)
  src5_train_iter_real = iter(src5_train_dataloader_real)
  src5_iter_per_epoch_real = len(src5_train_iter_real)

  src1_train_iter_fake = iter(src1_train_dataloader_fake)
  src1_iter_per_epoch_fake = len(src1_train_iter_fake)
  src2_train_iter_fake = iter(src2_train_dataloader_fake)
  src2_iter_per_epoch_fake = len(src2_train_iter_fake)
  src3_train_iter_fake = iter(src3_train_dataloader_fake)
  src3_iter_per_epoch_fake = len(src3_train_iter_fake)
  src4_train_iter_fake = iter(src4_train_dataloader_fake)
  src4_iter_per_epoch_fake = len(src4_train_iter_fake)
  src5_train_iter_fake = iter(src5_train_dataloader_fake)
  src5_iter_per_epoch_fake = len(src5_train_iter_fake)

  epoch = 1
  iter_per_epoch = 100
  
  net3 = fas_model_weighting2(config.gamma, config.beta,config.tgt_data,patch,pixel).to(device)

  lr_ = 0.0001
  for iter_num in range(22000 + 1):
    optimizer3 = optim.Adam(net3.parameters(), lr=lr_, weight_decay=0.000001)
    lr_ = 0.0001 * (rate/100)**(iter_num/100)

    if (iter_num % src1_iter_per_epoch_real == 0):
      src1_train_iter_real = iter(src1_train_dataloader_real)
    if (iter_num % src2_iter_per_epoch_real == 0):
      src2_train_iter_real = iter(src2_train_dataloader_real)
    if (iter_num % src3_iter_per_epoch_real == 0):
      src3_train_iter_real = iter(src3_train_dataloader_real)
    if (iter_num % src4_iter_per_epoch_real == 0):
      src4_train_iter_real = iter(src4_train_dataloader_real)
    if (iter_num % src5_iter_per_epoch_real == 0):
      src5_train_iter_real = iter(src5_train_dataloader_real)

    if (iter_num % src1_iter_per_epoch_fake == 0):
      src1_train_iter_fake = iter(src1_train_dataloader_fake)
    if (iter_num % src2_iter_per_epoch_fake == 0):
      src2_train_iter_fake = iter(src2_train_dataloader_fake)
    if (iter_num % src3_iter_per_epoch_fake == 0):
      src3_train_iter_fake = iter(src3_train_dataloader_fake)
    if (iter_num % src4_iter_per_epoch_fake == 0):
      src4_train_iter_fake = iter(src4_train_dataloader_fake)
    if (iter_num % src5_iter_per_epoch_fake == 0):
      src5_train_iter_fake = iter(src5_train_dataloader_fake)

    if (iter_num != 0 and iter_num % iter_per_epoch == 0):
      epoch = epoch + 1


    net3.train(True)
    optimizer3.zero_grad()
    ######### data prepare #########
    src1_img_real, src1_label_real = src1_train_iter_real.next()
    src1_img_real = src1_img_real.cuda()
    src1_label_real = src1_label_real.cuda()
    input1_real_shape = src1_img_real.shape[0]

    src2_img_real, src2_label_real = src2_train_iter_real.next()
    src2_img_real = src2_img_real.cuda()
    src2_label_real = src2_label_real.cuda()
    input2_real_shape = src2_img_real.shape[0]

    src3_img_real, src3_label_real = src3_train_iter_real.next()
    src3_img_real = src3_img_real.cuda()
    src3_label_real = src3_label_real.cuda()
    input3_real_shape = src3_img_real.shape[0]

    src4_img_real, src4_label_real = src4_train_iter_real.next()
    src4_img_real = src4_img_real.cuda()
    src4_label_real = src4_label_real.cuda()
    input4_real_shape = src4_img_real.shape[0]

    src5_img_real, src5_label_real = src5_train_iter_real.next()
    src5_img_real = src5_img_real.cuda()
    src5_label_real = src5_label_real.cuda()
    input5_real_shape = src5_img_real.shape[0]

    src1_img_fake, src1_label_fake = src1_train_iter_fake.next()
    src1_img_fake = src1_img_fake.cuda()
    src1_label_fake = src1_label_fake.cuda()
    input1_fake_shape = src1_img_fake.shape[0]

    src2_img_fake, src2_label_fake = src2_train_iter_fake.next()
    src2_img_fake = src2_img_fake.cuda()
    src2_label_fake = src2_label_fake.cuda()
    input2_fake_shape = src2_img_fake.shape[0]

    src3_img_fake, src3_label_fake = src3_train_iter_fake.next()
    src3_img_fake = src3_img_fake.cuda()
    src3_label_fake = src3_label_fake.cuda()
    input3_fake_shape = src3_img_fake.shape[0]

    src4_img_fake, src4_label_fake = src4_train_iter_fake.next()
    src4_img_fake = src4_img_fake.cuda()
    src4_label_fake = src4_label_fake.cuda()
    input4_fake_shape = src4_img_fake.shape[0]

    src5_img_fake, src5_label_fake = src5_train_iter_fake.next()
    src5_img_fake = src5_img_fake.cuda()
    src5_label_fake = src5_label_fake.cuda()
    input5_fake_shape = src5_img_fake.shape[0]

    if config.tgt_data in ['cefa', 'surf', 'wmca']:
      input_data = torch.cat([
          src1_img_real, src1_img_fake, src2_img_real, src2_img_fake,
          src3_img_real, src3_img_fake, src5_img_real, src5_img_fake
      ],
                             dim=0)
    else:
      input_data = torch.cat([
          src1_img_real, src1_img_fake, src2_img_real, src2_img_fake,
          src3_img_real, src3_img_fake, src4_img_real, src4_img_fake,
          src5_img_real, src5_img_fake
      ],
                             dim=0)

    if config.tgt_data in ['cefa', 'surf', 'wmca']:
      source_label = torch.cat([
          src1_label_real.fill_(1),
          src1_label_fake.fill_(0),
          src2_label_real.fill_(1),
          src2_label_fake.fill_(0),
          src3_label_real.fill_(1),
          src3_label_fake.fill_(0),
          src5_label_real.fill_(1),
          src5_label_fake.fill_(0)
      ],
                               dim=0)
    else:
      source_label = torch.cat([
          src1_label_real.fill_(1),
          src1_label_fake.fill_(0),
          src2_label_real.fill_(1),
          src2_label_fake.fill_(0),
          src3_label_real.fill_(1),
          src3_label_fake.fill_(0),
          src4_label_real.fill_(1),
          src4_label_fake.fill_(0),
          src5_label_real.fill_(1),
          src5_label_fake.fill_(0)
      ],
                               dim=0)

    ######### forward #########

    classifier_label_out, feature, cos_loss = net3(input_data, True)

    cls_loss = criterion['softmax'](classifier_label_out.narrow(
        0, 0, input_data.size(0)), source_label)

    total_loss = cls_loss + config.weight * cos_loss

    total_loss.backward()
    optimizer3.step()
    optimizer3.zero_grad()

    loss_classifier.update(cls_loss.item())
    acc = accuracy_net2(
        classifier_label_out.narrow(0, 0, input_data.size(0)),
        source_label,
        topk=(1,))
    classifer_top1.update(acc[0])

    if (iter_num != 0 and (iter_num + 1) % (iter_per_epoch) == 0):
      # 0:loss, 1:top-1, 2:EER, 3:HTER, 4:AUC, 5:threshold, 6:ACC_threshold
      valid_args = eval(test_dataloader, net3, True)
      # judge model according to HTER
      is_best = valid_args[3] <= best_model_HTER
      best_model_HTER = min(valid_args[3], best_model_HTER)
      threshold = valid_args[5]
      if (valid_args[3] <= best_model_HTER):
        best_model_ACC = valid_args[6]
        best_model_AUC = valid_args[4]

      save_list = [
          epoch, valid_args, best_model_HTER, best_model_ACC, best_model_ACER,
          threshold
      ]
      save_checkpoint(save_list, is_best, net3,
                      config.tgt_data + '.pth_SPP%s_sig%s_%s.tar'%(rate,patch,pixel))
      print('\r', end='', flush=True)
      log.write(
          '  %4.1f  |  %5.3f  %6.3f  %6.3f  %6.3f  |  %6.3f  %6.3f  |  %6.3f  %6.3f  %6.3f  | %s   %s'
          % ((iter_num + 1) / iter_per_epoch, valid_args[0], valid_args[6],
             valid_args[3] * 100, valid_args[4] * 100, loss_classifier.avg,
             classifer_top1.avg, float(best_model_ACC),
             float(best_model_HTER * 100), float(
                 best_model_AUC * 100), time_to_str(timer() - start, 'min'), 0))
      log.write('\n')
      time.sleep(0.01)

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--config', type=str, default='O')
  parser.add_argument('-seed', default=3407, type=int, help='set seed for model')
  args = parser.parse_args()

  if args.config == 'I':
    config = configI
  if args.config == 'C':
    config = configC
  if args.config == 'M':
    config = configM
  if args.config == 'O':
    config = configO
  if args.config == 'cefa':
    config = config_cefa
  if args.config == 'surf':
    config = config_surf
  if args.config == 'wmca':
    config = config_wmca

  for attr in dir(config):
    if attr.find('__') == -1:
      print('%s = %r' % (attr, getattr(config, attr)))
 
  set_seed(args)
  train(config)