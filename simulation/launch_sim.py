import sys

import dronekit
# Auxiliary scipy and numpy modules
import numpy as np
from scipy.spatial.transform import Rotation

print("Launching")

# Omniverse Isaac Sim imports
# Imports to start Isaac Sim from this script
from isaacsim import SimulationApp

# Start Isaac Sim's simulation environment
# Note: this simulation app must be instantiated right after the SimulationApp import, otherwise the simulator will crash
# as this is the object that will load all the extensions and load the actual simulator.
CONFIG = {"renderer": "RayTracedLighting", "headless": False}
simulation_app = SimulationApp(CONFIG)
import carb
import omni
import omni.graph.core as og
import omni.timeline
import usdrt.Sdf
from omni.isaac.core.prims import GeometryPrim, RigidPrim
from omni.isaac.core.utils import extensions, stage
from omni.isaac.core.world import World
from pxr import Gf, Usd, UsdGeom

# -----------------------------------
# The actual script should start here
# -----------------------------------

# enable ROS bridge extension
extensions.enable_extension("omni.isaac.ros2_bridge")

simulation_app.update()


class Drone:
    def __init__(self, vehicle_id, init_pos, world: World, usd_path):
        self._usd_path = usd_path
        self._init_pos = init_pos
        self._world = world
        self._drone_prim = None
        self.scale = 1.0

        self._dronekit_connection = dronekit.connect(
            "127.0.0.1:14553", wait_ready=True, timeout=999999, rate=120
        )

        self._create_prim(vehicle_id, usd_path, init_pos)
        self.set_world_position(init_pos)

        world.add_physics_callback(
            "update_drone_state", self.update_state_from_mavlink
        )

    def _create_prim(
        self, vehicle_id, usd_path, position=[0.0, 0.0, 0.0], orientation=None
    ):
        self.stage_path = f"/World/drone{vehicle_id}"
        stage.add_reference_to_stage(usd_path=usd_path, prim_path=self.stage_path)

        self._drone_prim = self._world.scene.add(
            GeometryPrim(
                prim_path=self.stage_path,
                name=f"drone_{vehicle_id}",
                position=position,
                orientation=orientation,
                scale=[self.scale, self.scale, self.scale],
                collision=True,
            )
        )

    def update_state_from_mavlink(self, args):
        args # is required function definition for the physics callback
        r = self._dronekit_connection._roll + np.pi / 2
        p = self._dronekit_connection._pitch
        y = self._dronekit_connection._yaw

        rot = Rotation.from_euler("xyz", [r, p, y], degrees=False)
        # quaternion: xyzw
        q = rot.as_quat()

        o = [q[3], q[0], q[1], q[2]]
        p = [
            self._dronekit_connection.location.local_frame.east,
            self._dronekit_connection.location.local_frame.north,
            -self._dronekit_connection.location.local_frame.down,
        ]
        if p[-1] is not None:
            # quaternion: wxyz
            self.set_world_pose(p, o)
        else:
            print("Drone location from dronekit is None")

    def get_world_pose(self):
        return self._drone_prim.get_world_pose()

    def set_world_pose(self, position, orientation):
        self._drone_prim.set_world_pose(position, orientation)

    def set_world_position(self, position):
        _, orientation = self._drone_prim.get_world_pose()
        self._drone_prim.set_world_pose(position, orientation)

    def set_orientation_z_angle(self, angle):
        position, _ = self._drone_prim.get_world_pose()
        o = Rotation.from_euler("XYZ", [0.0, 0.0, angle]).as_quat()
        orienatation = [o[3], o[0], o[1], o[2]]
        self._drone_prim.set_world_pose(position, orienatation)


# Locate Isaac Sim assets folder to load sample
usd_path = "omniverse://nucleusserver.andrew.cmu.edu/Projects/DSTA/Scenes/Tokyo_Spirit_Drone/Tokyo_Spirit_Drone_Sim.usd"
# make sure the file exists before we try to open it
try:
    result = omni.isaac.nucleus.is_file(usd_path)
except:
    result = False

if result:
    omni.usd.get_context().open_stage(usd_path)
else:
    carb.log_error(
        f"the usd path {usd_path} could not be opened, please make sure that {usd_path} is a valid usd file"
    )
    simulation_app.close()
    sys.exit()
# Wait two frames so that stage starts loading
simulation_app.update()
simulation_app.update()

print("Loading stage...")
from omni.isaac.core.utils.stage import is_stage_loading

while is_stage_loading():
    simulation_app.update()
print("Loading Complete")

world = World(stage_units_in_meters=1.0)

drone_usd = "omniverse://nucleusserver.andrew.cmu.edu/Library/Assets/Ascent_Aerosystems/Spirit_UAV/spirit_uav_red_yellow.usd"
drone = Drone("spirit_0", [0.0, 0.0, 0.7], world, usd_path=drone_usd)

# Creating a Camera prim
CAMERA_STAGE_PATH = drone.stage_path + "/Camera"
camera_prim = UsdGeom.Camera(omni.usd.get_context().get_stage().DefinePrim(CAMERA_STAGE_PATH, "Camera"))
xform_api = UsdGeom.XformCommonAPI(camera_prim)
xform_api.SetTranslate(Gf.Vec3d(0, 0, 0.1))
xform_api.SetRotate((0, 0, 0), UsdGeom.XformCommonAPI.RotationOrderXYZ)  # face forward
# xform_api.SetRotate((90, 0, 0), UsdGeom.XformCommonAPI.RotationOrderXYZ)  # face forward
camera_prim.GetHorizontalApertureAttr().Set(21)
camera_prim.GetVerticalApertureAttr().Set(16)
camera_prim.GetProjectionAttr().Set("perspective")
camera_prim.GetFocalLengthAttr().Set(24)
camera_prim.GetFocusDistanceAttr().Set(400)

simulation_app.update()

ROS_CAMERA_GRAPH_PATH = "/ROS_Camera"
# Creating an on-demand push graph with cameraHelper nodes to generate ROS image publishers

keys = og.Controller.Keys
(ros_camera_graph, _, _, _) = og.Controller.edit(
    {
        "graph_path": ROS_CAMERA_GRAPH_PATH,
        "evaluator_name": "push",
        "pipeline_stage": og.GraphPipelineStage.GRAPH_PIPELINE_STAGE_ONDEMAND,
    },
    {
        keys.CREATE_NODES: [
            ("OnTick", "omni.graph.action.OnTick"),
            ("createViewport", "omni.isaac.core_nodes.IsaacCreateViewport"),
            ("getRenderProduct", "omni.isaac.core_nodes.IsaacGetViewportRenderProduct"),
            ("setCamera", "omni.isaac.core_nodes.IsaacSetCameraOnRenderProduct"),
            ("cameraHelperRgb", "omni.isaac.ros2_bridge.ROS2CameraHelper"),
            ("cameraHelperInfo", "omni.isaac.ros2_bridge.ROS2CameraHelper"),
            ("cameraHelperDepth", "omni.isaac.ros2_bridge.ROS2CameraHelper"),
        ],
        keys.CONNECT: [
            ("OnTick.outputs:tick", "createViewport.inputs:execIn"),
            ("createViewport.outputs:execOut", "getRenderProduct.inputs:execIn"),
            ("createViewport.outputs:viewport", "getRenderProduct.inputs:viewport"),
            ("getRenderProduct.outputs:execOut", "setCamera.inputs:execIn"),
            ("getRenderProduct.outputs:renderProductPath", "setCamera.inputs:renderProductPath"),
            ("setCamera.outputs:execOut", "cameraHelperRgb.inputs:execIn"),
            ("setCamera.outputs:execOut", "cameraHelperInfo.inputs:execIn"),
            ("setCamera.outputs:execOut", "cameraHelperDepth.inputs:execIn"),
            ("getRenderProduct.outputs:renderProductPath", "cameraHelperRgb.inputs:renderProductPath"),
            ("getRenderProduct.outputs:renderProductPath", "cameraHelperInfo.inputs:renderProductPath"),
            ("getRenderProduct.outputs:renderProductPath", "cameraHelperDepth.inputs:renderProductPath"),
        ],
        keys.SET_VALUES: [
            ("createViewport.inputs:viewportId", 1),
            ("cameraHelperRgb.inputs:frameId", "sim_camera"),
            ("cameraHelperRgb.inputs:topicName", "rgb"),
            ("cameraHelperRgb.inputs:type", "rgb"),
            ("cameraHelperInfo.inputs:frameId", "sim_camera"),
            ("cameraHelperInfo.inputs:topicName", "camera_info"),
            ("cameraHelperInfo.inputs:type", "camera_info"),
            ("cameraHelperDepth.inputs:frameId", "sim_camera"),
            ("cameraHelperDepth.inputs:topicName", "depth"),
            ("cameraHelperDepth.inputs:type", "depth"),
            ("setCamera.inputs:cameraPrim", [usdrt.Sdf.Path(CAMERA_STAGE_PATH)]),
        ],
    },
)

# Run the ROS Camera graph once to generate ROS image publishers in SDGPipeline
og.Controller.evaluate_sync(ros_camera_graph)

simulation_app.update()



omni.timeline.get_timeline_interface().play()
# Run in test mode, exit after a fixed number of steps
while simulation_app.is_running():

    # Update the UI of the app and perform the physics step
    # world.step(render=True)
    simulation_app.update()

omni.timeline.get_timeline_interface().stop()
simulation_app.close()
