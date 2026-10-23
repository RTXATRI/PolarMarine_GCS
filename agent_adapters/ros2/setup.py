from setuptools import find_packages, setup

package_name = "polarmarine_ros2_adapter"

setup(
    name=package_name,
    version="1.0.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="PolarMarine",
    maintainer_email="engineering@polarmarine.local",
    description="PolarMarine GCS ROS2 device protocol adapter.",
    license="Proprietary",
    entry_points={
        "console_scripts": [
            "polarmarine_adapter = polarmarine_ros2_adapter.node:main",
        ],
    },
)
