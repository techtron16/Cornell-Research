#! /usr/bin/env python

import roslib
import rospy
import tf
from tf import transformations
import sys, time
from numpy import *
import _pyvicon
import math

class ViconPublisher:
    def __init__(self, host="128.84.189.209", port=801, \
        x_VICON_name="XtionJD:XtionJD <t-X>", y_VICON_name="XtionJD:XtionJD <t-Y>", z_VICON_name="XtionJD:XtionJD <t-Z>", \
        phi_VICON_name="XtionJD:XtionJD <a-X>", theta_VICON_name="XtionJD:XtionJD <a-Y>", psi_VICON_name="XtionJD:XtionJD <a-Z>"):
   # def __init__(self, host="10.0.0.102", port=800, x_VICON_name="GPSReceiverHelmet-goodaxes:GPSReceiverHelmet01 <t-X>", y_VICON_name="GPSReceiverHelmet-goodaxes:GPSReceiverHelmet01 <t-Y>", theta_VICON_name="GPSReceiverHelmet-goodaxes:GPSReceiverHelmet01 <a-Z>"):
        
        """
        Pose handler for VICON system
        host (string): The ip address of VICON system (default="10.0.0.102")
        port (int): The port of VICON system (default=800)
        x_VICON_name (string): The name of the stream for x pose of the robot in VICON system (default="SubjectName:SegmentName <t-X>")
        y_VICON_name (string): The name of the stream for y pose of the robot in VICON system (default="SubjectName:SegmentName <t-Y>")
        theta_VICON_name (string): The name of the stream for orintation of the robot in VICON system (default="SubjectName:SegmentName <a-Z>")
        """

        br = tf.TransformBroadcaster()

        self.host = host
        self.port = port
        self.x = x_VICON_name
        self.y = y_VICON_name
        self.z = z_VICON_name
        self.phi = phi_VICON_name
        self.theta = theta_VICON_name
        self.psi = psi_VICON_name

        self.s = _pyvicon.ViconStreamer()
        self.s.connect(self.host,self.port)

        self.s.selectStreams(["Time", self.x, self.y, self.z, self.phi, self.theta, self.psi])

        self.s.startStreams()
        rate = rospy.Rate(10.0)
        # Wait for first data to come in
        while self.s.getData() is None:
            print "Waiting for data..." 
            pass

        print "Stream acquired"
        while not rospy.is_shutdown():    
#           print self.s.getData()
            pose = self.getPose()
            print "pose: "
            print pose
	    A = math.sqrt(math.pow(pose[4],2)+math.pow(pose[5],2)+math.pow(pose[6],2))

            
	    W = math.cos(A/2)
   	    
   	    if A < 1e-15:
			xq = 0
			yq = 0
			zq = 0
	    else:
			xq = pose[4]/A*math.sin(A/2)
			yq = pose[5]/A*math.sin(A/2)
			zq = pose[6]/A*math.sin(A/2)
	    q = [xq,yq,zq,W]
        
            #TODO add a filter
            br.sendTransform((pose[1],pose[2],pose[3]),
                q,
                rospy.Time.now(),  # should we be use vicon time instead?
                "xtion",
                "vicon");

            br.sendTransform((0.02, 0.09, -0.025), transformations.quaternion_from_euler(0.04, 0.054, -0.045, 'rxyz'), rospy.Time.now(), "camera_link", "vicon_tf")
		
 	    rate.sleep()

# Is any sort of sleep command needed?
    def _stop(self):
        print "board pose handler quitting..."
        self.s.stopStreams()
        print "Terminated."

    def getPose(self, cached=False):

        (t, x, y, z, phi, theta, psi) = self.s.getData()
        (t, x, y, z, phi, theta, psi) = [t/100, x/1000, y/1000, z/1000, phi, theta, psi]

        return array([t, x, y, z, phi, theta, psi])

if __name__ == "__main__":
    rospy.init_node('xtion_publisher')
    try:
        ViconPublisher()
    except:
        pass
