#-*- coding:utf-8 -*-

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function


import os
import argparse
import torch
import torch.nn as nn
import torch.backends.cudnn as cudnn
from torch.autograd import Variable

import cv2
import time
import numpy as np
from PIL import Image

from data.config import cfg
from pyramidbox import build_net
from utils.augmentations import to_chw_bgr

parser = argparse.ArgumentParser(description='pyramidbox demo')
parser.add_argument('--img_path', default='./img',
                    help='Directory of images to demo')
parser.add_argument('--save_dir',
                    type=str, default='tmp/',
                    help='Directory for detect result')
parser.add_argument('--model',
                    type=str, default='weights/pyramidbox.pth',
                    help='trained model')
parser.add_argument('--thresh',
                    default=0.4, type=float,
                    help='Final confidence threshold')
parser.add_argument('--save_cropped_faces', default=False,
		    action='store_true')
args = parser.parse_args()


if not os.path.exists(args.save_dir):
    os.makedirs(args.save_dir)

use_cuda = torch.cuda.is_available()

if use_cuda:
    torch.set_default_tensor_type('torch.cuda.FloatTensor')
else:
    torch.set_default_tensor_type('torch.FloatTensor')


def detect(net, img_path, thresh, save_crops):
    img = Image.open(img_path)
    #orig_img = img
    #if img.mode == 'L':
     #   img = img.convert('RGB')
    #orig_img = np.array(orig_img)
    img = np.array(img)
    height, width, _ = img.shape
    max_im_shrink = np.sqrt(
        1200 * 1100 / (img.shape[0] * img.shape[1]))
    image = cv2.resize(img, None, None, fx=max_im_shrink,
                       fy=max_im_shrink, interpolation=cv2.INTER_LINEAR)

    x = to_chw_bgr(image)
    x = x.astype('float32')
    x -= cfg.img_mean
    x = x[[2, 1, 0], :, :]
    #x = x * cfg.scale

    x = Variable(torch.from_numpy(x).unsqueeze(0))
    if use_cuda:
        x = x.cuda()
    t1 = time.time()
    y = net(x)
    detections = y.data
    scale = torch.Tensor([img.shape[1], img.shape[0],
                          img.shape[1], img.shape[0]])

    for i in range(detections.size(1)):
        j = 0
        image_filename = os.path.join(args.save_dir, os.path.basename(img_path))
        while detections[0, i, j, 0] >= thresh:
            score = detections[0, i, j, 0]
            pt = (detections[0, i, j, 1:] * scale).cpu().numpy().astype(int)
            left_up, right_bottom = (pt[0], pt[1]), (pt[2], pt[3])
            j += 1

            if save_crops:
                # increase bbox by 10% on all sides
                face_width = pt[3] - pt[1]
                ten_percent_width = int(0.1 * face_width)
                face_height = pt[2] - pt[0]
                ten_percent_height = int(0.1 * face_height)

                # save cropped face images as face0-imagename, face1-imagename, etc.
                face = img[pt[1] - ten_percent_width:pt[3] + ten_percent_width, 
                           pt[0] - ten_percent_height:pt[2] + ten_percent_height]
                cv2.imwrite(os.path.join(args.save_dir, 'face{}-'.format(j) + os.path.basename(img_path)), cv2.cvtColor(face, cv2.COLOR_RGB2BGR))

            cv2.rectangle(img, left_up, right_bottom, (0, 0, 255), 2)

            conf = "{:.2f}".format(score)
            text_size, baseline = cv2.getTextSize(
                conf, cv2.FONT_HERSHEY_SIMPLEX, 0.3, 1)
            p1 = (left_up[0], left_up[1] - text_size[1])
            cv2.rectangle(img, (p1[0] - 2 // 2, p1[1] - 2 - baseline),
                          (p1[0] + text_size[0], p1[1] + text_size[1]), [255, 0, 0], -1)
            cv2.putText(img, conf, (p1[0], p1[
                        1] + baseline), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1, 8)

    t2 = time.time()
    print('detect:{} timer:{}'.format(img_path, t2 - t1))

    cv2.imwrite(image_filename, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))


if __name__ == '__main__':
    net = build_net('test', cfg.NUM_CLASSES)
    net.load_state_dict(torch.load(args.model))
    net.eval()

    if use_cuda:
        net.cuda()
        cudnn.benckmark = True

    img_list = [os.path.join(args.img_path, x)
                for x in os.listdir(args.img_path) if x.endswith('jpg')]
    for path in img_list:
        detect(net, path, args.thresh, args.save_cropped_faces)
