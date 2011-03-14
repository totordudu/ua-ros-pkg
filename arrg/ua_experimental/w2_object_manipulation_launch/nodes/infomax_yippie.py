#!/usr/bin/env python

# Author: Antons Rebguns

import math

import roslib; roslib.load_manifest('w2_object_manipulation_launch')
import rospy

from ua_audio_infomax.msg import Action as InfomaxAction
from ua_audio_infomax.srv import InfoMax
from ua_audio_infomax.srv import InfoMaxResponse
from ua_audio_capture.srv import StartAudioRecording
from ua_audio_capture.srv import StopAudioRecording
from ua_audio_capture.srv import classify
from ua_controller_msgs.msg import JointState as DynamixelJointState
from ax12_controller_core.srv import SetSpeed
from wubble2_robot.msg import WubbleGripperAction
from wubble2_robot.msg import WubbleGripperGoal

from pr2_controllers_msgs.msg import JointTrajectoryControllerState
from pr2_controllers_msgs.msg import JointTrajectoryAction
from pr2_controllers_msgs.msg import JointTrajectoryGoal

from tf import TransformListener

from actionlib import SimpleActionClient
from actionlib_msgs.msg import GoalStatus

from tabletop_object_detector.srv import TabletopSegmentation
from tabletop_object_detector.srv import TabletopSegmentationResponse
from tabletop_object_detector.msg import TabletopDetectionResult

from tabletop_collision_map_processing.srv import TabletopCollisionMapProcessing
from tabletop_collision_map_processing.srv import TabletopCollisionMapProcessingRequest

from object_manipulation_msgs.msg import PickupAction
from object_manipulation_msgs.msg import PickupActionGoal
from object_manipulation_msgs.msg import PickupGoal
from object_manipulation_msgs.msg import GraspableObject
from object_manipulation_msgs.msg import GraspPlanningErrorCode
from object_manipulation_msgs.msg import GraspHandPostureExecutionGoal
from object_manipulation_msgs.msg import GraspHandPostureExecutionAction
from object_manipulation_msgs.srv import GraspPlanning
from object_manipulation_msgs.srv import GraspPlanningRequest
from object_manipulation_msgs.srv import GraspStatus

from geometry_msgs.msg import PoseStamped
from geometry_msgs.msg import Quaternion
from geometry_msgs.msg import Point
from geometry_msgs.msg import Point32
from sensor_msgs.msg import JointState

from kinematics_msgs.srv import GetKinematicSolverInfo
from kinematics_msgs.srv import GetPositionIK
from kinematics_msgs.srv import GetPositionIKRequest
from kinematics_msgs.srv import GetPositionFK
from kinematics_msgs.srv import GetPositionFKRequest

from motion_planning_msgs.msg import PositionConstraint
from motion_planning_msgs.msg import OrientationConstraint
from motion_planning_msgs.msg import JointConstraint
from motion_planning_msgs.msg import ArmNavigationErrorCodes
from motion_planning_msgs.msg import AllowedContactSpecification
from motion_planning_msgs.msg import LinkPadding
from motion_planning_msgs.msg import OrderedCollisionOperations
from motion_planning_msgs.msg import CollisionOperation
from motion_planning_msgs.srv import GetMotionPlan
from motion_planning_msgs.srv import GetMotionPlanRequest

from move_arm_msgs.msg import MoveArmAction
from move_arm_msgs.msg import MoveArmGoal

from mapping_msgs.msg import AttachedCollisionObject
from mapping_msgs.msg import CollisionObjectOperation

from geometric_shapes_msgs.msg import Shape
from std_msgs.msg import Float64
from interpolated_ik_motion_planner.srv import SetInterpolatedIKMotionPlanParams



class ObjectCategorizer():
    def __init__(self):
        self.ARM_JOINTS = ('shoulder_pitch_joint',
                            'shoulder_pan_joint',
                            'upperarm_roll_joint',
                            'elbow_flex_joint',
                            'forearm_roll_joint',
                            'wrist_pitch_joint',
                            'wrist_roll_joint')
                            
        self.GRIPPER_LINKS = ('L9_right_finger_link',
                              'L8_left_finger_link',
                              'L7_wrist_roll_link')
                              
        self.READY_POSITION = (-1.650, -1.465, 3.130, -0.970, -1.427,  0.337,  0.046)
        self.LIFT_POSITION  = (-1.049, -1.241, 0.669, -0.960, -0.409, -0.072, -0.143)
        self.PLACE_POSITION = ( 0.261, -0.704, 1.470,  0.337,  0.910, -1.667, -0.026)
        
        # connect to tabletop segmentation service
        rospy.loginfo('waiting for tabletop_segmentation service')
        rospy.wait_for_service('/tabletop_segmentation')
        self.tabletop_segmentation_srv = rospy.ServiceProxy('/tabletop_segmentation', TabletopSegmentation)
        rospy.loginfo('connected to tabletop_segmentation service')
        
        # connect to collision map processing service
        rospy.loginfo('waiting for tabletop_collision_map_processing service')
        rospy.wait_for_service('/tabletop_collision_map_processing/tabletop_collision_map_processing')
        self.collision_map_processing_srv = rospy.ServiceProxy('/tabletop_collision_map_processing/tabletop_collision_map_processing', TabletopCollisionMapProcessing)
        rospy.loginfo('connected to tabletop_collision_map_processing service')
        
        # connect to grasp planning service
        rospy.loginfo('waiting for GraspPlanning service')
        rospy.wait_for_service('/GraspPlanning')
        self.grasp_planning_srv = rospy.ServiceProxy('/GraspPlanning', GraspPlanning)
        rospy.loginfo('connected to GraspPlanning service')
        
        # connect to move_arm action server
        rospy.loginfo('waiting for move_left_arm action server')
        self.move_arm_client = SimpleActionClient('/move_left_arm', MoveArmAction)
        self.move_arm_client.wait_for_server()
        rospy.loginfo('connected to move_left_arm action server')
        
        # connect to kinematics solver service
        rospy.loginfo('waiting for wubble_left_arm_kinematics/get_ik_solver_info service')
        rospy.wait_for_service('/wubble_left_arm_kinematics/get_ik_solver_info')
        self.get_solver_info_srv = rospy.ServiceProxy('/wubble_left_arm_kinematics/get_ik_solver_info', GetKinematicSolverInfo)
        rospy.loginfo('connected to wubble_left_arm_kinematics/get_ik_solver_info service')
        
        rospy.loginfo('waiting for wubble_left_arm_kinematics/get_ik service')
        rospy.wait_for_service('/wubble_left_arm_kinematics/get_ik')
        self.get_ik_srv = rospy.ServiceProxy('/wubble_left_arm_kinematics/get_ik', GetPositionIK)
        rospy.loginfo('connected to wubble_left_arm_kinematics/get_ik service')
        
        rospy.loginfo('waiting for wubble_left_arm_kinematics/get_fk service')
        rospy.wait_for_service('/wubble_left_arm_kinematics/get_fk')
        self.get_fk_srv = rospy.ServiceProxy('/wubble_left_arm_kinematics/get_fk', GetPositionFK)
        rospy.loginfo('connected to wubble_left_arm_kinematics/get_fk service')
        
        # connect to gripper action server
        rospy.loginfo('waiting for wubble_gripper_grasp_action')
        self.posture_controller = SimpleActionClient('/wubble_gripper_grasp_action', GraspHandPostureExecutionAction)
        self.posture_controller.wait_for_server()
        rospy.loginfo('connected to wubble_gripper_grasp_action')
        
        rospy.loginfo('waiting for wubble_grasp_status service')
        rospy.wait_for_service('/wubble_grasp_status')
        self.get_grasp_status_srv = rospy.ServiceProxy('/wubble_grasp_status', GraspStatus)
        rospy.loginfo('connected to wubble_grasp_status service')
        
        # connect to gripper action server
        rospy.loginfo('waiting for wubble_gripper_action')
        self.gripper_controller = SimpleActionClient('/wubble_gripper_action', WubbleGripperAction)
        self.gripper_controller.wait_for_server()
        rospy.loginfo('connected to wubble_gripper_action')
        
        # connect to audio saving services
        rospy.loginfo('waiting for audio_dump/start_audio_recording service')
        rospy.wait_for_service('audio_dump/start_audio_recording')
        self.start_audio_recording_srv = rospy.ServiceProxy('/audio_dump/start_audio_recording', StartAudioRecording)
        rospy.loginfo('connected to audio_dump/start_audio_recording service')
        
        rospy.loginfo('waiting for audio_dump/stop_audio_recording service')
        rospy.wait_for_service('audio_dump/stop_audio_recording')
        self.stop_audio_recording_srv = rospy.ServiceProxy('/audio_dump/stop_audio_recording', StopAudioRecording)
        rospy.loginfo('connected to audio_dump/stop_audio_recording service')
        
        rospy.loginfo('waiting for wrist_roll_controller service')
        rospy.wait_for_service('/wrist_roll_controller/set_speed')
        self.wrist_roll_velocity_srv = rospy.ServiceProxy('/wrist_roll_controller/set_speed', SetSpeed)
        rospy.loginfo('connected to wrist_roll_controller service')
        
        # connect to interpolated IK services
        rospy.loginfo('waiting for l_interpolated_ik_motion_plan_set_params service')
        rospy.wait_for_service('/l_interpolated_ik_motion_plan_set_params')
        self.interpolated_ik_params_srv = rospy.ServiceProxy('/l_interpolated_ik_motion_plan_set_params', SetInterpolatedIKMotionPlanParams)
        rospy.loginfo('connected to l_interpolated_ik_motion_plan_set_params service')
        
        rospy.loginfo('waiting for l_interpolated_ik_motion_plan service')
        rospy.wait_for_service('/l_interpolated_ik_motion_plan')
        self.interpolated_ik_srv = rospy.ServiceProxy('/l_interpolated_ik_motion_plan', GetMotionPlan)
        rospy.loginfo('connected to l_interpolated_ik_motion_plan service')
        
        rospy.loginfo('waiting for l_arm_controller/joint_trajectory_action')
        self.trajectory_controller = SimpleActionClient('/l_arm_controller/joint_trajectory_action', JointTrajectoryAction)
        self.trajectory_controller.wait_for_server()
        rospy.loginfo('connected to l_arm_controller/joint_trajectory_action')
        
        rospy.loginfo('waiting for classify service')
        rospy.wait_for_service('/classify')
        self.classification_srv = rospy.ServiceProxy('/classify', classify)
        rospy.loginfo('connected to classify service')
        
        # will publish to wrist roll joint controller for roll action
        self.wrist_roll_command_pub = rospy.Publisher('wrist_roll_controller/command', Float64)
        
        # will publish when objects are attached or detached to/from the gripper
        self.attached_object_pub = rospy.Publisher('/attached_collision_object', AttachedCollisionObject)
        
        # advertise InfoMax service
        rospy.Service('get_category_distribution', InfoMax, self.process_infomax_request)
        
        rospy.loginfo('all services contacted, object_categorization is ready to go')


    def move_arm_joint_goal(self, joint_names, joint_positions, allowed_contacts=[], link_padding=[], collision_operations=OrderedCollisionOperations()):
        goal = MoveArmGoal()
        goal.planner_service_name = 'ompl_planning/plan_kinematic_path'
        goal.motion_plan_request.planner_id = ''
        goal.motion_plan_request.group_name = 'left_arm'
        goal.motion_plan_request.num_planning_attempts = 3
        goal.motion_plan_request.allowed_planning_time = rospy.Duration(5.0)
        goal.motion_plan_request.goal_constraints.joint_constraints = [JointConstraint(j, p, 0.1, 0.1, 0.0) for (j,p) in zip(joint_names,joint_positions)]
        
        goal.motion_plan_request.allowed_contacts = allowed_contacts
        goal.motion_plan_request.link_padding = link_padding
        goal.motion_plan_request.ordered_collision_operations = collision_operations
        
        self.move_arm_client.send_goal(goal)
        finished_within_time = self.move_arm_client.wait_for_result(rospy.Duration(200.0))
        
        if not finished_within_time:
            self.move_arm_client.cancel_goal()
            rospy.loginfo('timed out trying to achieve a joint goal')
            return False
        else:
            state = self.move_arm_client.get_state()
            
            if state == GoalStatus.SUCCEEDED:
                rospy.loginfo('action finished: %s' % str(state))
                return True
            else:
                rospy.loginfo('action failed: %s' % str(state))
                return False


    def tuck_arm(self):
        """
        Moves the arm to the side out of the view of all sensors and fully
        opens a gripper. In this position the arm is ready to perform a grasp
        action.
        """
        if self.move_arm_joint_goal(self.ARM_JOINTS, self.READY_POSITION):
#            self.open_gripper()
            return True
        else:
            rospy.logerr('failed to tuck arm, aborting')
            return False


    def open_gripper(self):
        pg = GraspHandPostureExecutionGoal()
        pg.goal = GraspHandPostureExecutionGoal.RELEASE
        
        self.posture_controller.send_goal(pg)
        self.posture_controller.wait_for_result()


    def close_gripper(self):
        pg = GraspHandPostureExecutionGoal()
        pg.goal = GraspHandPostureExecutionGoal.GRASP
        
        self.posture_controller.send_goal(pg)
        self.posture_controller.wait_for_result()
        
        rospy.sleep(1)
        grasp_status = self.get_grasp_status_srv()
        return grasp_status.is_hand_occupied


    def gentle_close_gripper(self):
        self.close_gripper()
        
        goal = WubbleGripperGoal()
        goal.command = WubbleGripperGoal.CLOSE_GRIPPER
        goal.torque_limit = 0.0
        goal.dynamic_torque_control = False
        
        self.gripper_controller.send_goal(goal)
        self.gripper_controller.wait_for_result()


    def segment_objects(self):
        """
        Performs tabletop segmentation. If successful, returns a TabletopDetectionResult
        objct ready to be passed for processing to tabletop collision map processing node.
        """
        segmentation_result = self.tabletop_segmentation_srv()
        
        if segmentation_result.result != TabletopSegmentationResponse.SUCCESS or not segmentation_result.clusters:
            rospy.logerr('TabletopSegmentation did not find any clusters')
            return None
            
        rospy.loginfo('TabletopSegmentation found %d clusters' % len(segmentation_result.clusters))
        
        tdr = TabletopDetectionResult()
        tdr.table = segmentation_result.table
        tdr.clusters = segmentation_result.clusters
        tdr.result = segmentation_result.result
        
        return tdr


    def reset_collision_map(self):
        req = TabletopCollisionMapProcessingRequest()
        req.detection_result = TabletopDetectionResult()
        req.reset_collision_models = True
        req.reset_attached_models = True
        req.reset_static_map = True
        req.take_static_collision_map = False
        
        self.collision_map_processing_srv(req)
        rospy.loginfo('collision map reset')


    def update_collision_map(self, tabletop_detection_result):
        rospy.loginfo('collision_map update in progress')
        
        req = TabletopCollisionMapProcessingRequest()
        req.detection_result = tabletop_detection_result
        req.reset_collision_models = True
        req.reset_attached_models = True
        req.reset_static_map = True
        req.take_static_collision_map = True
        req.desired_frame = 'base_link'
        
        res = self.collision_map_processing_srv(req)
        
        rospy.loginfo('collision_map update is done')
        rospy.loginfo('there are %d graspable objects %s, collision support surface name is "%s"' %
                      (len(res.graspable_objects), res.collision_object_names, res.collision_support_surface_name))
                      
        return res


    def find_ik_for_grasping_pose(self, pose_stamped):
        solver_info = self.get_solver_info_srv()
        arm_joints = solver_info.kinematic_solver_info.joint_names
        
        req = GetPositionIKRequest()
        req.timeout = rospy.Duration(5.0)
        req.ik_request.ik_link_name = 'L7_wrist_roll_link';
        req.ik_request.pose_stamped = pose_stamped
        
        rospy.loginfo('waiting for current joint states')
        current_state = rospy.wait_for_message('/joint_states', JointState)
        rospy.loginfo('recevied current joint states')
        
        req.ik_request.ik_seed_state.joint_state.name = arm_joints
        req.ik_request.ik_seed_state.joint_state.position = [current_state.position[current_state.name.index(j)] for j in arm_joints]
        
        ik_result = self.get_ik_srv(req)
        
        if ik_result.error_code.val == ArmNavigationErrorCodes.SUCCESS:
            return ik_result.solution
        else:
            rospy.logerr('Inverse kinematics failed')
            return None


    def find_grasp_pose(self, target, collision_object_name='', collision_support_surface_name=''):
        """
        target = GraspableObject
        collision_object_name = name of target in collision map
        collision_support_surface_name = name of surface target is touching
        """
        
        req = GraspPlanningRequest()
        req.arm_name = 'left_arm'
        req.target = target
        req.collision_object_name = collision_object_name
        req.collision_support_surface_name = collision_support_surface_name
        
        rospy.loginfo('trying to find a good grasp for graspable object %s' % collision_object_name)
        grasping_result = self.grasp_planning_srv(req)
        
        if grasping_result.error_code.value != GraspPlanningErrorCode.SUCCESS:
            rospy.logerr('unable to find a feasable grasp, aborting')
            return None
            
        pose_stamped = PoseStamped()
        pose_stamped.header.frame_id = grasping_result.grasps[0].grasp_posture.header.frame_id
        pose_stamped.pose = grasping_result.grasps[0].grasp_pose
        
        rospy.loginfo('found good grasp, looking for corresponding IK')
        
        return self.find_ik_for_grasping_pose(pose_stamped)


    def grasp(self, tabletop_collision_map_processing_result):
        target = tabletop_collision_map_processing_result.graspable_objects[0]
        collision_object_name = tabletop_collision_map_processing_result.collision_object_names[0]
        collision_support_surface_name = tabletop_collision_map_processing_result.collision_support_surface_name
        
        ik_solution = self.find_grasp_pose(target, collision_object_name, collision_support_surface_name)
        
        if ik_solution:
            ordered_collision_operations = OrderedCollisionOperations()
            collision_operation = CollisionOperation()
            collision_operation.object1 = CollisionOperation.COLLISION_SET_OBJECTS
            collision_operation.object2 = 'l_end_effector'
            collision_operation.operation = CollisionOperation.DISABLE
            collision_operation.penetration_distance = 0.01
            ordered_collision_operations.collision_operations = [collision_operation]
            
            gripper_paddings = [LinkPadding(l,0.0) for l in self.GRIPPER_LINKS]
            
            if not self.move_arm_joint_goal(ik_solution.joint_state.name, ik_solution.joint_state.position, link_padding=gripper_paddings, collision_operations=ordered_collision_operations):
                rospy.logerr('failed to move arm to grasping position, aborting')
                return None
                
            rospy.sleep(0.5)
            
            # record grasping sound with 0.5 second padding before and after
            self.start_audio_recording_srv(InfomaxAction.GRASP, self.category_id)
            rospy.sleep(0.5)
            grasp_successful = self.close_gripper()
            rospy.sleep(0.5)
            
            if grasp_successful:
                sound = self.stop_audio_recording_srv(True)
                resp = self.classification_srv(sound.recorded_sound)
                print 'GRASP RESULT'
                print resp
                
                obj = AttachedCollisionObject()
                obj.object.header.stamp = rospy.Time.now()
                obj.object.header.frame_id = 'L7_wrist_roll_link'
                obj.object.operation.operation = CollisionObjectOperation.ATTACH_AND_REMOVE_AS_OBJECT
                obj.object.id = collision_object_name
                obj.link_name = 'L7_wrist_roll_link'
                obj.touch_links = self.GRIPPER_LINKS
                
                self.attached_object_pub.publish(obj)
                rospy.sleep(2)
                return resp.beliefs
            else:
                self.stop_audio_recording_srv(False)
                return None
        else:
            rospy.logerr('failed to find an IK for requested grasping pose, aborting')
            return None


    def create_pose_stamped(self, pose, frame_id='base_link'):
        """
        Creates a PoseStamped message from a list of 7 numbers (first three are
        position and next four are orientation:
        pose = [px,py,pz, ox,oy,oz,ow]
        """
        m = PoseStamped()
        m.header.frame_id = frame_id
        m.header.stamp = rospy.Time()
        m.pose.position = Point(*pose[0:3])
        m.pose.orientation = Quaternion(*pose[3:7])
        return m


    #pretty-print list to string
    def pplist(self, list_to_print):
        return ' '.join(['%5.3f'%x for x in list_to_print])


    def get_interpolated_ik_motion_plan(self, start_pose, goal_pose, start_angles, joint_names, pos_spacing=0.01,
                                        rot_spacing=0.1, consistent_angle=math.pi/9, collision_aware=True,
                                        collision_check_resolution=1, steps_before_abort=-1, num_steps=0,
                                        ordered_collision_operations=None, frame='base_footprint', start_from_end=0,
                                        max_joint_vels=[1.5]*7, max_joint_accs=[1.0]*7):
                                        
        res = self.interpolated_ik_params_srv(num_steps,
                                              consistent_angle,
                                              collision_check_resolution,
                                              steps_before_abort,
                                              pos_spacing,
                                              rot_spacing,
                                              collision_aware,
                                              start_from_end,
                                              max_joint_vels,
                                              max_joint_accs)
                                       
        req = GetMotionPlanRequest()
        req.motion_plan_request.start_state.joint_state.name = joint_names
        req.motion_plan_request.start_state.joint_state.position = start_angles
        req.motion_plan_request.start_state.multi_dof_joint_state.pose = start_pose.pose
        req.motion_plan_request.start_state.multi_dof_joint_state.child_frame_id = 'L7_wrist_roll_link'
        req.motion_plan_request.start_state.multi_dof_joint_state.frame_id = start_pose.header.frame_id
        
        pos_constraint = PositionConstraint()
        pos_constraint.position = goal_pose.pose.position
        pos_constraint.header.frame_id = goal_pose.header.frame_id
        req.motion_plan_request.goal_constraints.position_constraints = [pos_constraint,]
        
        orient_constraint = OrientationConstraint()
        orient_constraint.orientation = goal_pose.pose.orientation
        orient_constraint.header.frame_id = goal_pose.header.frame_id
        req.motion_plan_request.goal_constraints.orientation_constraints = [orient_constraint,]
        
        req.motion_plan_request.link_padding = [LinkPadding(l,0.0) for l in self.GRIPPER_LINKS]
        
        if ordered_collision_operations is not None:
            req.motion_plan_request.ordered_collision_operations = ordered_collision_operations
            
        res = self.interpolated_ik_srv(req)
        
        error_code_dict = { ArmNavigationErrorCodes.SUCCESS: 0,
                            ArmNavigationErrorCodes.COLLISION_CONSTRAINTS_VIOLATED: 1,
                            ArmNavigationErrorCodes.PATH_CONSTRAINTS_VIOLATED: 2,
                            ArmNavigationErrorCodes.JOINT_LIMITS_VIOLATED: 3,
                            ArmNavigationErrorCodes.PLANNING_FAILED: 4 }
                            
        trajectory_len = len(res.trajectory.joint_trajectory.points)
        trajectory = [res.trajectory.joint_trajectory.points[i].positions for i in range(trajectory_len)]
        vels = [res.trajectory.joint_trajectory.points[i].velocities for i in range(trajectory_len)]
        times = [res.trajectory.joint_trajectory.points[i].time_from_start for i in range(trajectory_len)]
        error_codes = [error_code_dict[error_code.val] for error_code in res.trajectory_error_codes]
        
        rospy.loginfo("trajectory:")
        
        for ind in range(len(trajectory)):
            rospy.loginfo("error code "+ str(error_codes[ind]) + " pos : " + self.pplist(trajectory[ind]))
        
        rospy.loginfo("")
        
        for ind in range(len(trajectory)):
            rospy.loginfo("time: " + "%5.3f  "%times[ind].to_sec() + "vels: " + self.pplist(vels[ind]))
            
        goal = JointTrajectoryGoal()
        for i, p in enumerate(res.trajectory.joint_trajectory.points):
            if res.trajectory_error_codes[i].val == ArmNavigationErrorCodes.SUCCESS:
                goal.trajectory.points.append(p)
        goal.trajectory.joint_names = res.trajectory.joint_trajectory.joint_names
        goal.trajectory.points = goal.trajectory.points[1:] # skip the 0 velocity point
        goal.trajectory.header.stamp = rospy.Time.now() + rospy.Duration(1.0)
        
        self.trajectory_controller.send_goal(goal)
        self.trajectory_controller.wait_for_result()


    def check_cartesian_path_lists(self, approachpos, approachquat, grasppos, graspquat, start_angles, pos_spacing=0.01,
                                   rot_spacing=0.1, consistent_angle=math.pi/6.0, collision_aware=True,
                                   collision_check_resolution=1, steps_before_abort=-1, num_steps=0,
                                   ordered_collision_operations=None, frame='base_link'):
                                   
        start_pose = self.create_pose_stamped(approachpos+approachquat, frame)
        goal_pose = self.create_pose_stamped(grasppos+graspquat, frame)
        
        self.get_interpolated_ik_motion_plan(start_pose, goal_pose, start_angles, self.ARM_JOINTS, pos_spacing, rot_spacing,
                                             consistent_angle, collision_aware, collision_check_resolution,
                                             steps_before_abort, num_steps, ordered_collision_operations, frame)

    def pre_lift(self, ordered_collision_operations):
        current_state = rospy.wait_for_message('l_arm_controller/state', JointTrajectoryControllerState)
        start_angles = current_state.actual.positions
        
        full_state = rospy.wait_for_message('/joint_states', JointState)
        
        req = GetPositionFKRequest()
        req.header.frame_id = 'base_link'
        req.fk_link_names = ['L7_wrist_roll_link']
        req.robot_state.joint_state = full_state
        pose = self.get_fk_srv(req).pose_stamped[0].pose
        
        frame_id = 'base_link'
        
        approachpos =  [pose.position.x, pose.position.y, pose.position.z]
        approachquat = [pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w]
        
        grasppos = [0.0, 0.0, 0.1]
        graspquat = approachquat[:]
        
        self.check_cartesian_path_lists(approachpos, approachquat, grasppos, graspquat, start_angles, frame=frame_id, ordered_collision_operations=ordered_collision_operations)


    # needs grasp action to be performed first
    def lift(self, tabletop_collision_map_processing_result):
        collision_support_surface_name = tabletop_collision_map_processing_result.collision_support_surface_name
        
        ordered_collision_operations = OrderedCollisionOperations()
        
        collision_operation = CollisionOperation()
        collision_operation.object1 = CollisionOperation.COLLISION_SET_ATTACHED_OBJECTS
        collision_operation.object2 = collision_support_surface_name
        collision_operation.operation = CollisionOperation.DISABLE
        ordered_collision_operations.collision_operations = [collision_operation]
        
        collision_operation = CollisionOperation()
        collision_operation.object1 = 'l_end_effector'
        collision_operation.object2 = collision_support_surface_name
        collision_operation.operation = CollisionOperation.DISABLE
        ordered_collision_operations.collision_operations.append(collision_operation)
        
        gripper_paddings = [LinkPadding(l,0.0) for l in self.GRIPPER_LINKS]
        
        obj = AttachedCollisionObject()
        obj.object.header.stamp = rospy.Time.now()
        obj.object.header.frame_id = 'L7_wrist_roll_link'
        obj.object.operation.operation = CollisionObjectOperation.REMOVE
        obj.object.id = collision_support_surface_name
        obj.link_name = 'L7_wrist_roll_link'
        obj.touch_links = self.GRIPPER_LINKS
        
        self.attached_object_pub.publish(obj)
        rospy.sleep(2)
        
        self.start_audio_recording_srv(InfomaxAction.LIFT, self.category_id)
        #self.pre_lift(ordered_collision_operations)
        
        if self.move_arm_joint_goal(self.ARM_JOINTS, self.LIFT_POSITION, link_padding=gripper_paddings, collision_operations=ordered_collision_operations):
            sound = self.stop_audio_recording_srv(True)
            resp = self.classification_srv(sound.recorded_sound)
            
            print 'LIFT RESULT'
            print resp
            return resp.beliefs
        else:
            self.stop_audio_recording_srv(False)
            rospy.logerr('failed to lift arm')
            return None


    # needs grasp and lift to be performed first
    def drop(self, tabletop_collision_map_processing_result):
        collision_object_name = tabletop_collision_map_processing_result.collision_object_names[0]
        
        self.start_audio_recording_srv(InfomaxAction.DROP, self.category_id)
        rospy.sleep(0.5)
        self.open_gripper()
        rospy.sleep(1.5)
        sound = self.stop_audio_recording_srv(True)
        resp = self.classification_srv(sound.recorded_sound)
        print 'DROP RESULT'
        print resp
        
        # delete the object that we just dropped since don't really know where it will land
        obj = AttachedCollisionObject()
        obj.object.header.stamp = rospy.Time.now()
        obj.object.header.frame_id = 'L7_wrist_roll_link'
        obj.object.operation.operation = CollisionObjectOperation.REMOVE
        obj.object.id = collision_object_name
        obj.link_name = 'L7_wrist_roll_link'
        obj.touch_links = self.GRIPPER_LINKS
        
        self.attached_object_pub.publish(obj)
        rospy.sleep(2)
        
        return resp.beliefs


    def place(self, tabletop_collision_map_processing_result):
        collision_object_name = tabletop_collision_map_processing_result.collision_object_names[0]
        collision_support_surface_name = tabletop_collision_map_processing_result.collision_support_surface_name
        
        gripper_paddings = [LinkPadding(l,0.0) for l in self.GRIPPER_LINKS]
        
        # move arm to target pose and disable collisions between the object an the table
        ordered_collision_operations = OrderedCollisionOperations()
        collision_operation = CollisionOperation()
        collision_operation.object1 = CollisionOperation.COLLISION_SET_ATTACHED_OBJECTS
        collision_operation.object2 = collision_support_surface_name
        collision_operation.operation = CollisionOperation.DISABLE
        ordered_collision_operations.collision_operations = [collision_operation]
        
        self.start_audio_recording_srv(InfomaxAction.PLACE, self.category_id)
        
        if self.move_arm_joint_goal(self.ARM_JOINTS, self.PLACE_POSITION, link_padding=gripper_paddings, collision_operations=ordered_collision_operations):
            self.open_gripper()
            rospy.sleep(0.5)
            sound = self.stop_audio_recording_srv(True)
            resp = self.classification_srv(sound.recorded_sound)
            print 'PLACE RESULT'
            print resp
            
            obj = AttachedCollisionObject()
            obj.object.header.stamp = rospy.Time.now()
            obj.object.header.frame_id = 'L7_wrist_roll_link'
            obj.object.operation.operation = CollisionObjectOperation.DETACH_AND_ADD_AS_OBJECT
            obj.object.id = collision_object_name
            obj.link_name = 'L7_wrist_roll_link'
            obj.touch_links = self.GRIPPER_LINKS
            
            self.attached_object_pub.publish(obj)
            
            rospy.sleep(2)
            return resp.beliefs
        else:
            self.stop_audio_recording_srv(False)
            rospy.logerr('failed to place arm')
            return None


    def shake_roll(self, tabletop_collision_map_processing_result):
        desired_velocity = 11.0
        distance = 2.5
        threshold = 0.2
        self.wrist_roll_velocity_srv(2.0)
        self.wrist_roll_command_pub.publish(distance)
        
        while rospy.wait_for_message('wrist_roll_controller/state', DynamixelJointState).current_pos < distance-threshold:
            rospy.sleep(10e-3)
            
        self.wrist_roll_velocity_srv(desired_velocity)
        self.start_audio_recording_srv(InfomaxAction.SHAKE_ROLL, self.category_id)
        rospy.sleep(0.5)
        
        for i in range(2):
            self.wrist_roll_command_pub.publish(-distance)
            while rospy.wait_for_message('wrist_roll_controller/state', DynamixelJointState).current_pos > -distance+threshold:
                rospy.sleep(10e-3)
                
            self.wrist_roll_command_pub.publish(distance)
            while rospy.wait_for_message('wrist_roll_controller/state', DynamixelJointState).current_pos < distance-threshold:
                rospy.sleep(10e-3)
                
        rospy.sleep(0.5)
        sound = self.stop_audio_recording_srv(True)
        resp = self.classification_srv(sound.recorded_sound)
        print 'SHAKE_ROLL RESULT'
        print resp
        
        self.wrist_roll_velocity_srv(2.0)
        self.wrist_roll_command_pub.publish(0.0)
        
        rospy.sleep(2)
        return resp.beliefs


    def reset_robot(self, tabletop_collision_map_processing_result=None):
        if tabletop_collision_map_processing_result:
            obj = AttachedCollisionObject()
            obj.object.header.stamp = rospy.Time.now()
            obj.object.header.frame_id = 'L7_wrist_roll_link'
            obj.object.operation.operation = CollisionObjectOperation.REMOVE
            obj.object.id = tabletop_collision_map_processing_result.collision_object_names[0]
            obj.link_name = 'L7_wrist_roll_link'
            obj.touch_links = self.GRIPPER_LINKS
            
            self.attached_object_pub.publish(obj)
            rospy.sleep(2)
            
        self.open_gripper()
        self.reset_collision_map()
        if not self.tuck_arm(): return False
        self.gentle_close_gripper()
        return True


    # receive an InfoMax service request containing object ID and desired action
    def process_infomax_request(self, req):
        self.object_names = req.objectNames
        self.action_names = req.actionNames
        self.num_categories = req.numCats
        self.category_id = req.catID
        
        prereqs = {InfomaxAction.GRASP:      [self.grasp],
                   InfomaxAction.LIFT:       [self.grasp, self.lift],
                   InfomaxAction.SHAKE_ROLL: [self.grasp, self.lift, self.shake_roll],
                   InfomaxAction.DROP:       [self.grasp, self.lift, self.drop],
                   InfomaxAction.PLACE:      [self.grasp, self.lift, self.place]}
                   
        if not self.reset_robot(): return None
        
        # find a graspable object on the floor
        tdr = self.segment_objects()
        if tdr is None: return None
        
        # mark floor and object poitions in the collision map as known
        tcmpr = self.update_collision_map(tdr)
        
        self.open_gripper()
        
        # initialize as uniform distribution
        beliefs = [1.0/self.num_categories] * self.num_categories
        actions = prereqs[req.actionID.val]
        
        for act in actions:
            beliefs = act(tcmpr)
            
            if not beliefs:
                self.reset_robot()
                return None
            
        if not self.reset_robot(tcmpr): return None
        
        res = InfoMaxResponse()
        res.beliefs = beliefs
        res.location = self.category_id
        return res


if __name__ == '__main__':
    rospy.init_node('infomax_yippie_node', anonymous=True)
    oc = ObjectCategorizer()
    oc.reset_robot()
    rospy.spin()

