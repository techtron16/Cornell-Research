#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Fri Mar  9 12:46:02 2018

@author: jonathan
"""

import tensorflow as tf
import numpy as np
import math
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import random as rand
from random import shuffle
import time

import rospy
from nav_msgs.msg import OccupancyGrid
from std_msgs.msg import Int32MultiArray

from env_characterization.srv import *

occ_map = OccupancyGrid()

NUM_CLASSES = 2

IMAGE_SIZE = 28
IMAGE_PIXELS = IMAGE_SIZE**2

tf.logging.set_verbosity(tf.logging.INFO)

def cnn_model_fn(features, labels, mode):
    # Input layer
    input_layer = tf.reshape(features["x"], [-1, 28, 28, 1])
    
    # Convolutional layer #1
    conv1 = tf.layers.conv2d(
            inputs=input_layer,
            filters=32,
            kernel_size=[5, 5],
            padding="same",
            activation=tf.nn.relu)
    
    # Pooling Layer #1
    pool1 = tf.layers.max_pooling2d(inputs=conv1, pool_size=[2, 2], strides=2)
    
    # Convolutional Layer #2
    conv2 = tf.layers.conv2d(
            inputs=pool1,
            filters=64,
            kernel_size=[5, 5],
            padding="same",
            activation=tf.nn.relu)
    pool2 = tf.layers.max_pooling2d(inputs=conv2, pool_size=[2, 2], strides=2)
    
    #Dense Layer
    pool2_flat = tf.reshape(pool2, [-1, 7 * 7 * 64])
    dense = tf.layers.dense(inputs=pool2_flat, units=1024, activation=tf.nn.relu)
    dropout = tf.layers.dropout(
            inputs=dense, rate=0.4, training=mode == tf.estimator.ModeKeys.TRAIN)
    
    logits = tf.layers.dense(inputs=dropout, units=2)
    
    predictions={
            "classes": tf.argmax(input=logits, axis=1),
            "probabilities": tf.nn.softmax(logits, name="softmax_tensor")
            }
    
    if mode == tf.estimator.ModeKeys.PREDICT:
        return tf.estimator.EstimatorSpec(mode=mode, predictions=predictions)
    
    #Calculate Loss (for both TRAIN and EVAL modes)
    loss = tf.losses.sparse_softmax_cross_entropy(labels=labels, logits=logits)
    
    # Configure the Training Op (for TRAIN mode)
    if mode == tf.estimator.ModeKeys.TRAIN:
        optimizer = tf.train.GradientDescentOptimizer(learning_rate=0.001)
        train_op = optimizer.minimize(
                loss=loss,
                global_step=tf.train.get_global_step())
        return tf.estimator.EstimatorSpec(mode=mode, loss=loss, train_op=train_op)
    
    #Add evaluation metrics (for EVAL mode)
    eval_metric_ops = {
            "accuracy": tf.metrics.accuracy(
                    labels=labels, predictions=predictions["classes"])}
    return tf.estimator.EstimatorSpec(
            mode=mode, loss=loss, eval_metric_ops=eval_metric_ops)
    
def callback(data):
    #rospy.loginfo(rospy.get_caller_id() + "Me hear message")
    global occ_map
    occ_map = data
    
def handle_classify_map(req):
    snippets = req.partitions
    
    mnist_classifier = tf.estimator.Estimator(
            model_fn=cnn_model_fn, model_dir="/home/jonathan/image_db/mnist_convnet_model")
    
    print np.size(snippets, 0)
    
    print ("Got Here")
    
    characters = np.array([np.float32(np.array(snippets[i].data) / 100.0 - 0.5) for i in range(0, np.size(snippets, 0))])
    
    print characters[50]
    
    pred_input_fn = tf.estimator.inputs.numpy_input_fn(
        x={"x": characters},
        num_epochs=1,
        shuffle=False)
    
    results = mnist_classifier.predict(pred_input_fn)
    classes = OccupancyGrid()
    data = []
    features = []
    for idx, p in enumerate(results):
        #print max(p["probabilities"]), p["classes"], idx
        if max(p["probabilities"]) >= 0.5:
            data.append(p["classes"])
            features.append(p["classes"])
        else:
            data.append(0)
    
    return classify_mapResponse(classes)
    
#    for i in range(0, np.size(snippets)):
#        snip_data = np.float32(np.array(snippets[i].data) / 100.0)

def main(unused_argv):
    rospy.init_node('classifier', anonymous=True)
    rospy.Subscriber("occ_map", OccupancyGrid, callback)
    pub = rospy.Publisher("/classifications", OccupancyGrid, queue_size=10)
    
    s = rospy.Service('classify_map', classify_map, handle_classify_map)
    
    #Assemble datasets
    train_data = []
    train_labels = []
    
    set0 = 180
    set1 = 180
    for i in range(1, set0):
        filename0 = "/home/jonathan/image_db/flat" + str(i) + ".png"
        raw_image = mpimg.imread(filename0)
        train_data.append(np.reshape(raw_image, (IMAGE_PIXELS)))
        train_labels.append(0)
    
    for i in range(1, set1):
        filename1 = "/home/jonathan/image_db/ledge" + str(i) + ".png"
    
        raw_image = mpimg.imread(filename1)
        train_data.append(np.reshape(raw_image, (IMAGE_PIXELS)))
        train_labels.append(1)
        
    eval_data = []
    eval_labels = []

    for i in range(10):
        filename_test = "/home/jonathan/image_db/ledge_test" + str(i) + ".png"
    
        raw_image = mpimg.imread(filename_test)
        eval_data.append(np.reshape(raw_image, (IMAGE_PIXELS)))
        eval_labels.append(1)
        
    for i in range(8):
        filename_test = "/home/jonathan/image_db/flat_t" + str(i) + ".png"
    
        raw_image = mpimg.imread(filename_test)
        eval_data.append(np.reshape(raw_image, (IMAGE_PIXELS)))
        eval_labels.append(0)
        
    #Convert lists to arrays for numpy input fn
    train_data = np.array(train_data)
    train_labels = np.array(train_labels)
    eval_data = np.array(eval_data)
    eval_labels = np.array(eval_labels)
    
    #Create the Estimator
    mnist_classifier = tf.estimator.Estimator(
            model_fn=cnn_model_fn, model_dir="/home/jonathan/image_db/mnist_convnet_model")
    
    # Set up logging for predictions
    # Log the values in the "Softmax" tensor with label "probabilities"
    tensors_to_log = {"probabilities": "softmax_tensor"}
    logging_hook = tf.train.LoggingTensorHook(
            tensors=tensors_to_log, every_n_iter=50)
    
    #Train the model
#    train_input_fn = tf.estimator.inputs.numpy_input_fn(
#            x={"x": train_data},
#            y=train_labels,
#            batch_size=100,
#            num_epochs=None,
#            shuffle=True)
#    mnist_classifier.train(
#            input_fn=train_input_fn,
#            steps=2000,
#            hooks=[logging_hook])
    
#    pred_input_fn = tf.estimator.inputs.numpy_input_fn(
#            x={"x": train_data[0]},
#            num_epochs=1,
#            shuffle=False)
#        
#    results = mnist_classifier.predict(pred_input_fn)
#    
#    for i, p in enumerate(results):
#        print i, p
#    
#    print results
    
#    while (occ_map.data == [] and not rospy.is_shutdown()):
#        time.sleep(0.1)
#    
#    img_data = []
#    img_label = []
#    img_data.append(occ_map.data)
#    img_label.append(1)
#    img_data = np.float32(np.array(img_data) / 100.0)
#    img_label = np.array(img_label)
    
    #Evaluate the model and print results
    eval_input_fn = tf.estimator.inputs.numpy_input_fn(
            x={"x": eval_data},
            y=eval_labels,
            num_epochs=1,
            shuffle=False)
    eval_results = mnist_classifier.evaluate(input_fn=eval_input_fn)
    print(eval_results)
    
    while not rospy.is_shutdown():
        time.sleep(0.1)
    
    pred_input_fn = tf.estimator.inputs.numpy_input_fn(
            x={"x": train_data[0:]},
            num_epochs=1,
            shuffle=False)
            
    results = mnist_classifier.predict(input_fn=pred_input_fn)
    
    test = [p["classes"] for idx, p in enumerate(results)]
    
    classes = OccupancyGrid()
    
    classes.header.frame_id = "map"
    classes.data = test
    classes.info.resolution = 0.02
    classes.info.height = 179
    classes.info.width = 2
    
    pub.publish(classes)
    
    #print classes
    
if __name__ == "__main__":
    tf.app.run()