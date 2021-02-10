#!/bin/bash
# A script to install Spinnaker
echo "========================================================================================"
echo "Welcome to the Spinnaker 8 installation setup!"
echo "========================================================================================"
echo "This setup will create a new directory called 'spinnaker' in the HBP installation folder and download all required files to this directory."
echo "After that, the Spinnaker binaries will be build from sources so please make sure that you have a C-compiler installed and added to the path."
printf "\033[1;33mWould you like to install SpiNNaker on your machine? (Y/n)\033[0m\n"
read -rt 5 p

if [ "$p" == "Y" -o "$p" == "y" ]
then
# NRRPLT-7989
# As of 2020-11-10 pip version of SPyNNaker8 doesn't work with PyNN 0.9.5.
# Install from pip when it will.

  no_install_msg="SpiNNaker support is DISABLED."

  # Create a directory for the spinnaker tools
  mkdir -p "$HBP"/spinnaker || { printf '\nERROR: SpiNNaker is already installed, please remove the $HBP/spinnaker directory and retry'; exit 1; }
  cd "$HBP"/spinnaker
  git clone https://github.com/SpiNNakerManchester/SupportScripts.git

  # Run the support script to fetch all repositories
  cd $HBP/spinnaker || { echo ERROR; exit 1; }
  source $NRP_VIRTUAL_ENV/bin/activate || { echo ERROR; exit 1; }
  SupportScripts/install.sh 8 -y
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
  SupportScripts/setup.sh || { printf "\nERROR: SpiNNUtils setup.sh - %s" "${no_install_msg}"; return 1; }
  SupportScripts/automatic_make.sh || { printf "\nERROR: SpiNNUtils make -  %s" "${no_install_msg}"; return 1; }

  python -m spynnaker8.setup_pynn || { printf "\nERROR: spynnaker8.setup_pynn - %s" "${no_install_msg}"; return 1; }

  python -c "import pyNN.spiNNaker"
  deactivate

  echo
  echo "========================================================================================"
  echo "Spinnaker 8 has been successfully installed on your system."
  echo "You can now use the SpiNNaker board for experiments in the HBP Neurorobotics Platform."
  echo
  echo 'WARNING: Please, edit $HOME/.spynnaker.cfg before running your first SpiNNaker simulation'
  echo "========================================================================================"
else
  echo
  echo "=================================================="
  echo "Spinnaker 8 has NOT been installed on your machine"
  echo "=================================================="
fi

echo
