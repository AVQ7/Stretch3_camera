#!/bin/bash
VERSION=`python src/stretch/version.py`
echo "Building docker image with tag hellorobotinc/stretch-ai-ros2-bridge:$VERSION"
SKIP_ASKING="false"
for arg in "$@"
do
    case $arg in
        -y|--yes)
            yn="y"
            SKIP_ASKING="true"
            shift
            ;;
        *)
            shift
            # unknown option
            ;;
    esac
done
if [ "$SKIP_ASKING" == "false" ]; then
    read -p "Verify that this is correct. Proceed? (y/n) " yn
    if [ "$answer" == "${answer#[Yy]}" ] ;then
        echo "Building docker image..."
    else
        echo "Exiting..."
        exit 1
    fi
fi
# Build the docker image with the current tag.
docker build -t hellorobotinc/stretch-ai-ros2-bridge . -f docker/Dockerfile.ros2
docker push hellorobotinc/stretch-ai-ros2-bridge:$VERSION
docker tag hellorobotinc/stretch-ai-ros2-bridge:$VERSION hellorobotinc/stretch-ai-ros2-bridge:latest
docker push hellorobotinc/stretch-ai-ros2-bridge:latest
