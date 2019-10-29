#!/bin/bash
# A script to install Spinnaker

echo "Welcome to the Spinnaker 8 installation setup!"
echo "This setup will create a new directory called 'spinnaker' in the HBP installation folder and download all required files to this directory." 
echo "After that, the Spinnaker binaries will be build from sources so please make sure that you have a C-compiler installed and added to the path."
printf "\033[1;33mWould you like to install SpiNNaker on your machine? (Y/n)\033[0m\n"
read -t 5 p
if [ "$p" == "Y" -o "$p" == "y" ]
then
  # TODO: Instead we should modify the python dependencies for the NRP project
  # Activate the platform virtual env and install the Python dependencies
  source $NRP_VIRTUAL_ENV/bin/activate
  pip install "appdirs>=1.4.2,<2.0.0" future "numpy>=1.12,<1.9999"  "scipy>=0.16.0" "six>=1.8.0" "pylru>=1" enum34 future lxml jsonschema sortedcollections
  pip install  "rig>=2.0.0,<3.0.0" futures enum-compat pytz tzlocal "requests>=2.4.1" matplotlib
  pip install  csa "quantities>=0.12.1" "pynn>=0.9.2,<0.10" "lazyarray>=0.2.9,<=0.4.0" "neo>=0.5.2,< 0.7.0"
  deactivate

  # Create a directory for the spinnaker tools
  mkdir $HBP/spinnaker && cd $HBP/spinnaker || { echo ERROR; exit 1; }
  git clone https://github.com/SpiNNakerManchester/SupportScripts.git || { echo ERROR; exit 1; }

  # Run the support script to fetch all repositories
  cd $HBP/spinnaker || { echo ERROR; exit 1; }
  source $NRP_VIRTUAL_ENV/bin/activate || { echo ERROR; exit 1; }
  SupportScripts/install.sh PyNN8
  deactivate

  # Set up the C environment variables
  export SPINN_DIRS=$HBP/spinnaker/spinnaker_tools
  export PATH=$PATH:$SPINN_DIRS/tools
  export PERL5LIB=$SPINN_DIRS/tools
  export NEURAL_MODELLING_DIRS=$HBP/spinnaker/sPyNNaker/neural_modelling

  # Install the ARM compiler
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends curl git gcc-arm-none-eabi libnewlib-arm-none-eabi 

  # Build everything
  cd $HBP/spinnaker
  source $NRP_VIRTUAL_ENV/bin/activate
  SupportScripts/setup.sh
  SupportScripts/automatic_make.sh
	 
  python -m spynnaker8.setup_pynn
 
  python -c "import pyNN.spiNNaker"
  deactivate

  echo "Spinnaker 8 was successfullly installed on your system."
  echo "You can now use the Spinnaker board for experiments in the HBP Neuro­robotics Plat­form."

else
  echo "Spinnaker was not installed on your machine."
fi



