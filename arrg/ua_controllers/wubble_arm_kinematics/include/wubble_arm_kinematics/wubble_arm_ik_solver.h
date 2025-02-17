//Software License Agreement (BSD License)

//Copyright (c) 2010, Antons Rebguns
//Copyright (c) 2008, Willow Garage, Inc.
//All rights reserved.

//Redistribution and use in source and binary forms, with or without
//modification, are permitted provided that the following conditions
//are met:

// * Redistributions of source code must retain the above copyright
//   notice, this list of conditions and the following disclaimer.
// * Redistributions in binary form must reproduce the above
//   copyright notice, this list of conditions and the following
//   disclaimer in the documentation and/or other materials provided
//   with the distribution.
// * Neither the name of Willow Garage, Inc. nor the names of its
//   contributors may be used to endorse or promote products derived
//   from this software without specific prior written permission.

//THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
//"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
//LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
//FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
//COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
//INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
//BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
//LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
//CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
//LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
//ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
//POSSIBILITY OF SUCH DAMAGE.

#ifndef WUBBLE_ARM_IK_SOLVER_H
#define WUBBLE_ARM_IK_SOLVER_H

#include <urdf/model.h>
#include <kdl/chainiksolver.hpp>
#include <wubble_arm_kinematics/wubble_arm_ik.h>
#include <wubble_arm_kinematics/wubble_arm_kinematics_utils.h>
#include <kinematics_msgs/GetKinematicSolverInfo.h>
#include <kinematics_msgs/PositionIKRequest.h>
#include <geometry_msgs/PoseStamped.h>
#include <tf_conversions/tf_kdl.h>

namespace wubble_arm_kinematics
{
  static const int NO_IK_SOLUTION = -1;
  static const int TIMED_OUT = -2;

  class WubbleArmIKSolver : public KDL::ChainIkSolverPos
  {
    public:

    /** @class
     *  @brief ROS/KDL based interface for the inverse kinematics of the Wubble arm
     *  @author Antons Rebguns, based on code by Sachin Chitta <sachinc@willowgarage.com>
     *
     *  This class provides a KDL based interface to the inverse kinematics of the Wubble arm. It inherits from the KDL::ChainIkSolverPos class
     *  but also exposes additional functionality to return multiple solutions from an inverse kinematics computation.
     */
    WubbleArmIKSolver(const urdf::Model &robot_model,
                      const std::string &root_frame_name,
                      const std::string &tip_frame_name,
                      const double &search_discretization_angle);

    ~WubbleArmIKSolver() {};

    /**
     * @brief The Wubble inverse kinematics solver
     */
    WubbleArmIK wubble_arm_ik_;

    /**
     * @brief Indicates whether the solver has been successfully initialized
     */
    bool active_;

    /**
     * @brief The KDL solver interface that is required to be implemented. NOTE: This method only returns a solution
     * if it exists for the free parameter value passed in. To search for a solution in the entire workspace use the CartToJntSearch
     * method detailed below.
     *
     * @return < 0 if no solution is found
     * @param q_init The initial guess for the inverse kinematics solution.
     * @param p_in A KDL::Frame representation of the position of the end-effector for which the IK is being solved.
     * @param q_out A single inverse kinematic solution (if it exists).
     */
    int CartToJnt(const KDL::JntArray& q_init,
                  const KDL::Frame& p_in,
                  KDL::JntArray& q_out);

    /**
     * @brief An extension of the KDL solver interface to return all solutions found. NOTE: This method only returns a solution
     * if it exists for the free parameter value passed in. To search for a solution in the entire workspace use the CartToJntSearch
     * method detailed below.
     *
     * @return < 0 if no solution is found
     * @param q_init The initial guess for the inverse kinematics solution.
     * @param p_in A KDL::Frame representation of the position of the end-effector for which the IK is being solved.
     * @param q_out A std::vector of KDL::JntArray containing all found solutions.
     */
    int CartToJnt(const KDL::JntArray& q_init,
                  const KDL::Frame& p_in,
                  std::vector<KDL::JntArray> &q_out);

     /**
     * @brief This method searches for and returns the first set of solutions it finds.
     *
     * @return < 0 if no solution is found
     * @param q_in The initial guess for the inverse kinematics solution.
     * @param p_in A KDL::Frame representation of the position of the end-effector for which the IK is being solved.
     * @param q_out A std::vector of KDL::JntArray containing all found solutions.
     * @param timeout The amount of time (in seconds) to spend looking for a solution.
     */
    int CartToJntSearch(const KDL::JntArray& q_in,
                        const KDL::Frame& p_in,
                        std::vector<KDL::JntArray> &q_out,
                        const double &timeout);

     /**
     * @brief This method searches for and returns the closest solution to the initial guess in the first set of solutions it finds.
     *
     * @return < 0 if no solution is found
     * @param q_in The initial guess for the inverse kinematics solution.
     * @param p_in A KDL::Frame representation of the position of the end-effector for which the IK is being solved.
     * @param q_out A std::vector of KDL::JntArray containing all found solutions.
     * @param timeout The amount of time (in seconds) to spend looking for a solution.
     */
    int CartToJntSearch(const KDL::JntArray& q_in,
                        const KDL::Frame& p_in,
                        KDL::JntArray &q_out,
                        const double &timeout);
    /**
       @brief A method to get chain information about the serial chain that the IK operates on
       @param response This class gets populated with information about the joints that IK operates on, including joint names and limits.
    */
    void getSolverInfo(kinematics_msgs::KinematicSolverInfo &response);

     /**
     * @brief This method searches for and returns the first solution it finds that also satisifies both user defined callbacks.
     *
     * @return < 0 if no solution is found
     * @param q_init The initial guess for the inverse kinematics solution.
     * @param p_in A KDL::Frame representation of the position of the end-effector for which the IK is being solved.
     * @param q_out A std::vector of KDL::JntArray containing all found solutions.
     * @param desired_pose_callback A callback function to which the desired pose is passed in
     * @param solution_callback A callback function to which IK solutions are passed in
     */
    int CartToJntSearch(const KDL::JntArray& q_in,
                        const KDL::Frame& p_in,
                        KDL::JntArray &q_out,
                        const double &timeout,
                        arm_navigation_msgs::ArmNavigationErrorCodes &error_code,
                        const boost::function<void(const KDL::JntArray&, const KDL::Frame&, arm_navigation_msgs::ArmNavigationErrorCodes&)> &desired_pose_callback,
                        const boost::function<void(const KDL::JntArray&, const KDL::Frame&, arm_navigation_msgs::ArmNavigationErrorCodes&)> &solution_callback);

    std::string getFrameId();

    private:

    bool getCount(int &count, const int &max_count, const int &min_count);
    double search_discretization_angle_;
    std::string root_frame_name_;
  };
}
#endif// WUBBLE_ARM_IK_SOLVER_H

