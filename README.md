# AirLab-Autonomy-Stack


# Requirements
You need at least 25GB free to install the Docker image.

Have some nice GPU to run Isaac Sim locally.

# Setup

```
git clone --recursive -j8 git@github.com:castacks/AirLab-Autonomy-Stack.git
```


Install the Omniverse launcher download from this link:
``` 
wget https://install.launcher.omniverse.nvidia.com/installers/omniverse-launcher-linux.AppImage
```


Follow these instructions to setup Nucleus : https://airlab.slite.com/app/docs/X8dZ8w5S3GP9tw


If you are using the Ascent Spirit drone download the SITL software packages from this link:
https://drive.google.com/file/d/1UxgezaTrHe4WJ28zsVeRhv1VYfOU5VK8/view?usp=drive_link

Then unzip the file  AscentAeroSystemsSITLPackage.zip  in this folder:
```
cd AirLab-Autonomy-Stack/simulation/AscentAeroSystems
unzip AscentAeroSystemsSITLPackage.zip -d .
```


# Build and run the Docker image
```bash
cd AirLab-Autonomy-Stack/docker/
# build the image, it is named airlab-autonomy-dev:latest
docker compose --profile build build
# start docker compose service/container
docker compose up -d 
```

# Launch
Launch autonomy stack controls package:
```bash
# start a new terminal in docker container
docker compose exec airlab_autonomy_dev bash

# in docker
bws && sws # build workspace and source workspace. these are aliases in ~/.bashrc
ros2 launch ros_ws/src/robot/autonomy/controls/launch/launch_controls.yaml
```

Launch simulator (Isaac Sim and Ascent SITL):
```bash
# start another terminal in docker container
docker compose exec airlab_autonomy_dev bash

# in docker
ISAACSIM_PYTHON simulation/launch_sim.py
```

# Move Robot
```bash
# start another terminal in docker container
docker compose exec airlab_autonomy_dev bash

# in docker
# set drone mode to GUIDED
ros2 service call /controls/mavros/set_mode mavros_msgs/SetMode "custom_mode: 'GUIDED'"
# ARM
ros2 service call /controls/mavros/cmd/arming mavros_msgs/srv/CommandBool "{value: True}"
# TAKEOFF
ros2 service call /controls/mavros/cmd/takeoff mavros_msgs/srv/CommandTOL "{altitude: 5}"
# FLY TO POSITION. Put whatever position you want
ros2 topic pub /controls/mavros/setpoint_position/local geometry_msgs/PoseStamped "{ header: { stamp: { sec: 0, nanosec: 0 }, frame_id: 'base_link' }, pose: { position: { x: 10.0, y: 0.0, z: 20.0 }, orientation: { x: 0.0, y: 0.0, z: 0.0, w: 1.0 } } }" -1
```