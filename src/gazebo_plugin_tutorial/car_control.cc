#include <gazebo/gazebo.hh>
#include <gazebo/physics/physics.hh>
#include <gazebo/physics/Joint.hh>
#include <gazebo/physics/JointController.hh>
#include <gazebo/physics/Model.hh>
#include <gazebo/physics/PhysicsTypes.hh>

#include <gazebo/transport/transport.hh>
#include <gazebo/msgs/msgs.hh>

#include <thread>
#include "ros/ros.h"
#include "ros/callback_queue.h"
#include "ros/subscribe_options.h"
#include "std_msgs/Float32.h"
#include <geometry_msgs/Twist.h>

using namespace std;

namespace gazebo
{
  class CarControl : public ModelPlugin
  {
    private:      
      physics::ModelPtr smore0, smoreF, smoreFL, smoreFR, smoreB, smoreBL, smoreBR;
      vector<vector<bool>> controlType;
      vector<vector<double>> targetVals;
      
    /// \brief A node used for transport
    private: transport::NodePtr node;
    
    /// \brief A subscriber to a named topic.
    private: transport::SubscriberPtr sub;
    
    /// \brief Pointer to the model.
    private: physics::ModelPtr model;

    /// \brief Pointer to the joint.
    private: physics::JointPtr joint;

    /// \brief A PID controller for the joint.
    private: common::PID pid;
    
    /// \brief A node used for ROS transport
    private: std::unique_ptr<ros::NodeHandle> rosNode;
    
    /// \brief A ROS subscriber
    private: ros::Subscriber rosSub;
    
    /// \brief A ROS callbackqueue that helps process messages
    private: ros::CallbackQueue rosQueue;
    
    ///\brief A thread that keps running the rosQueue
    private: std::thread rosQueueThread;
    
    public: virtual void Load(physics::ModelPtr _model, sdf::ElementPtr _sdf)
    {
      // Safety check
      if (_model->GetJointCount() == 0)
      {
	std::cerr << "Invalid joint count, Car Control plugin not loaded\n";
	return;
      }
      
      // Store the model pointer for convenience.
      this->model = _model;
      
      //Module List: SMORE0, SMORE_F, SMORE_FL, SMORE_FR, SMORE_B, SMORE_BL, SMORE_BR
      //Joint List: left_wheel_hinge, right_wheel_hinge, front_wheel_hinge, center_hinge
      
      //controlType vector for pos or vel control: 0 - pos, 1 - vel
      vector<bool> panVel = {1, 1, 1, 0};
      vector<bool> panPos = {1, 1, 0, 0};
      vector<bool> allPos = {0, 0, 0, 0};
      vector<bool> carPan = {0, 0, 1, 0};
      
      this->controlType = {allPos, allPos, carPan, carPan, allPos, carPan, carPan};
      
      //Vector of target values
      this->targetVals = vector<vector<double>>(this->model->NestedModels().size(), vector<double>(4, 0.0));
      
      //Set car wheel camber angles
      targetVals[2][3] = 0.2584;
      targetVals[3][3] = 0.2584;
      targetVals[5][3] = 0.2584;
      targetVals[6][3] = 0.2854;
      
      UpdateControl();
      
      this->node = transport::NodePtr(new transport::Node());
      
      #if GAZEBO_MAJOR_VERSION < 8
      this->node->Init(this->model->GetWorld()->GetName());
      #else
      this->node->Init(this->model->GetWorld()->Name());
      #endif
      
      if (!ros::isInitialized())
      {
	int argc = 0;
	char ** argv = NULL;
	ros::init(argc, argv, "gazebo_client", ros::init_options::NoSigintHandler);
      }
      
      // Create our ROS node. This acts in a similar manner to the Gazebo node
      this->rosNode.reset(new ros::NodeHandle("gazebo_client"));
      
      // Create a named topic, and subscribe to it.
      ros::SubscribeOptions so = ros::SubscribeOptions::create<geometry_msgs::Twist>(
	"/turtlebot_teleop/cmd_vel", 1, boost::bind(&CarControl::OnRosMsg, this, _1),
								  ros::VoidPtr(), &this->rosQueue);
      this->rosSub = this->rosNode->subscribe(so);
      
      // Spin up the queue helper thread.
      this->rosQueueThread = std::thread(std::bind(&CarControl::QueueThread, this));
    }
    
    /// \brief Handle an incoming message from ROS
    /// \param[in] _msg A float value that is used to set the velocity
    /// of the Velodyne.
    public: void OnRosMsg(const geometry_msgs::TwistConstPtr &_msg)
    {
      double v = _msg->linear.x;
      double w = _msg->angular.z;
      this->SetVelocity(v, w);
    }
    
    /// \brief ROS helper function that processes messages
    private: void QueueThread()
    {
      static const double timeout = 0.01;
      while (this->rosNode->ok())
      {
	this->rosQueue.callAvailable(ros::WallDuration(timeout));
      }
    }
    
    /// \brief Set the velocity of the Velodyne
    /// \param[in] _vel New target velocity
    public: void SetVelocity(const double &v, const double &w)
    {
      double eps = 0.2;
      double right = v + eps * w;
      double left = v - eps * w;
      
      targetVals[2][2] = -left;
      targetVals[3][2] = right;
      targetVals[5][2] = -left;
      targetVals[6][2] = right;
      
      UpdateControl();
    }
    
    public: void UpdateControl()
    {
      for (int i = 0; i < this->model->NestedModels().size(); i++)
      {
	physics::ModelPtr smore = this->model->NestedModels()[i];
	for (int j = 0; j < smore->GetJoints().size(); j++)
	{
	  physics::JointPtr motor = smore->GetJoints()[j];
	  //cout << motor->GetScopedName() << " : " << targetVals[i][j] << " (" << controlType[i][j] << ")" << endl;
	  if (controlType[i][j])
	  {
	    //smore->GetJointController()->SetVelocityPID(motor->GetScopedName(), common::PID(1, 0, 0));
	    //smore->GetJointController()->SetVelocityTarget(motor->GetScopedName(), targetVals[i][j]);
	    
	    motor->SetParam("vel", 0, targetVals[i][j]);
	  }
	  else
	  {
	    smore->GetJointController()->SetPositionPID(motor->GetScopedName(), common::PID(5, 10, 0.3, 1, -1));
	    smore->GetJointController()->SetPositionTarget(motor->GetScopedName(), targetVals[i][j]);
	  }
	}
      }
    }
  };
  
  //Register this plugin with the simulator
  GZ_REGISTER_MODEL_PLUGIN(CarControl)
}