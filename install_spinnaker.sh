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

  # TODO: Remove this later if the NRP supports the newest Spinnaker version
  # Checkout all working commits:
  cd $HBP/spinnaker
  cd DataSpecification
  git checkout eb71b0799ab615b7e0ad84293aed2399a139c01d
  cd ../IntroLab
  git checkout 65309789b1f06620f6e5b61c54bc78488523ebb3
  cd ../PACMAN
  git checkout 56b39e589ad650ab01b0c3bc5eb95ab80e1d76b1
  cd ../PyNN8Examples
  git checkout 595a5d1564f9bfd4acfa03957e8a8b6f0afa18ea
  cd ../spalloc
  git checkout 2555054da9197b465f4d6c759b7aba919cf0352f
  cd ../SpiNNakerGraphFrontEnd
  git checkout 57afc269400a96bd1e1ec033748139e151f2fa8e
  cd ../spinnaker_tools
  git checkout 9655a20453472d55c4b64ca8ff89d6949ccd84fa
  cd ../spinn_common
  git checkout 7e2a3cb93f1facdac459b304f2c343019c88695e
  cd ../SpiNNFrontEndCommon
  git checkout cc523e6e91678bffe96754a3c98ed1fc7657c2a8
  cd ../SpiNNMachine
  git checkout b7a003cddb967921d442a2b1c709dd07b51f04a0
  cd ../SpiNNMan
  git checkout d016d68292e09edb370e362ece302d7c565f2bff
  cd ../SpiNNStorageHandlers
  git checkout 9a41b5aeef0a4b80ff4fa4f2441f8d9b905fb54e
  cd ../SpiNNUtils
  git checkout 76c84249519532ed6cfbcde1784b277e7086b14b
  cd ../sPyNNaker
  git checkout d3ae1611efd3780561d2ee8b89a03a4f573d3e90
  cd ../sPyNNaker8
  git checkout 391e098147fecd18f0e0a0888276fb5554ccd403
  cd ../sPyNNaker8NewModelTemplate
  git checkout 423e9084f7cc9395c1ec9d1d7f19e7440acc045f
  cd ../sPyNNakerExternalDevicesPlugin
  git checkout a71e9aa6f3bf507169d076f0bc13b747d9d98122
  cd ../sPyNNakerExtraModelsPlugin
  git checkout 58b4652a9263f8a4071b289c942914e88cea0e59
  cd ../sPyNNakerVisualisers
  git checkout e93af37fae27751989aa1fb0dbbca56045de9e22
  cd ../SupportScripts
  git checkout fc313deb83cb1e7e0f4aa6a0f1f24b47e9f5c23a

  # Set up the C environment variables
  export SPINN_DIRS=$HBP/spinnaker/spinnaker_tools
  export PATH=$PATH:$SPINN_DIRS/tools
  export PERL5LIB=$SPINN_DIRS/tools
  export NEURAL_MODELLING_DIRS=$HBP/spinnaker/sPyNNaker/neural_modelling

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



