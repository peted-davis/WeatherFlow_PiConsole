#!/usr/bin/env bash

# Automated installer and updater for the WeatherFlow PiConsole. Modified
# heavily from the PiHole and PiVPN installers.
# Copyright (C) 2018-2021 Peter Davis

# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.

# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.

# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.

# GET INVOKING USER
# ------------------------------------------------------------------------------
if [[ "${EUID}" -eq 0 ]]; then
    USER=$SUDO_USER
else
    USER=$USER
fi

# DEFINE INSTALLER VARIABLES
# ------------------------------------------------------------------------------
# Download and install directories
CONSOLEDIR=/home/${USER}/wfpiconsole/
DLDIR=${CONSOLEDIR}/temp/

# Package manager commands
PKG_MANAGER="apt-get"
PKG_UPDATE_CACHE="${PKG_MANAGER} update"
PKG_UPDATE_INSTALL="${PKG_MANAGER} dist-upgrade -y"
PKG_UPDATE_COUNT="${PKG_MANAGER} -s -o Debug::NoLocking=true upgrade | grep -c ^Inst || true"
PKG_NEW_INSTALL=(${PKG_MANAGER} --yes install)

# Python PIP commands
PIP_INSTALL="python3 -m pip install --user"
PIP_UPDATE="python3 -m pip install --user --upgrade"

# wfpiconsole and Kivy dependencies
WFPICONSOLE_DEPENDENCIES=(git curl rng-tools build-essential python3-dev python3-pip python3-setuptools
                          libssl-dev libffi6 libffi-dev libatlas-base-dev jq)
KIVY_DEPENDENCIES_ARM=(pkg-config libgl1-mesa-dev libgles2-mesa-dev libgstreamer1.0-dev
                       gstreamer1.0-plugins-{bad,base,good,ugly} gstreamer1.0-{omx,alsa}
                       libmtdev-dev xclip xsel libjpeg-dev libsdl2-dev libsdl2-image-dev
                       libsdl2-mixer-dev libsdl2-ttf-dev)
KIVY_DEPENDENCIES=(ffmpeg libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev
                   libportmidi-dev libswscale-dev libavformat-dev libavcodec-dev zlib1g-dev
                   libgstreamer1.0-dev gstreamer1.0-plugins-base gstreamer1.0-plugins-good)

# Python modules and versions
KIVY_VERSION="2.0.0"
PYTHON_MODULES=(cython==0.29.24
                cryptography==35.0.0
                autobahn[twisted]==21.3.1
                pyasn1-modules==0.2.8
                service-identity==21.1.0
                numpy==1.21.4
                pytz==2021.3
                ephem==4.1
                pillow==8.4.0
                packaging==21.2
                pyOpenSSL==21.0.0
                distro==1.6.0)

# Github repositories
KIVY_REPO="https://github.com/kivy/kivy/archive/"$KIVY_VERSION".zip"
WFPICONSOLE_REPO="peted-davis/WeatherFlow_PiConsole"
WFPICONSOLE_MAIN="https://github.com/"$WFPICONSOLE_REPO"/tarball/main"
WFPICONSOLE_BETA="https://github.com/"$WFPICONSOLE_REPO"/tarball/develop"
WFPICONSOLE_TAGS="https://api.github.com/repos/"$WFPICONSOLE_REPO"/tags"
WFPICONSOLE_RELEASES="https://api.github.com/repos/"$WFPICONSOLE_REPO"/releases/latest"
WFPICONSOLE_MAIN_UPDATE="https://raw.githubusercontent.com/"$WFPICONSOLE_REPO"/main/wfpiconsole.sh"
WFPICONSOLE_BETA_UPDATE="https://raw.githubusercontent.com/"$WFPICONSOLE_REPO"/develop/wfpiconsole.sh"

# DEFINE INSTALLER PREAMBLE
# ------------------------------------------------------------------------------
# -e option instructs bash to immediately exit if any command [1] has a non-zero
# exit status.
set -e

# Define installer colors
if [[ -f "${coltable}" ]]; then
    source ${coltable}
else
    COL_NC='\e[0m'
    COL_LIGHT_GREEN='\e[1;32m'
    COL_LIGHT_RED='\e[1;31m'
    TICK="[${COL_LIGHT_GREEN}✓${COL_NC}]"
    CROSS="[${COL_LIGHT_RED}✗${COL_NC}]"
    INFO="[i]"
    DONE="${COL_LIGHT_GREEN} done!${COL_NC}"
    OVER="\\r\\033[K"
fi

# Find the number of  rows and columns in terminal. Will default to 80x24 if it
# can not be detected.
if (tput lines &> /dev/null); then
    rows=$(tput lines)
else
    rows=$(printf '%d' 80)
fi
if (tput cols &> /dev/null); then
    columns=$(tput cols)
else
    columns=$(printf '%d' 24)
fi

# Divide the number of rows and columns by two so
# the dialogs take up half of the screen.
r=$(( rows / 2 ))
c=$(( columns / 2 ))
# Unless the screen is tiny
r=$(( r < 20 ? 20 : r ))
c=$(( c < 70 ? 70 : c ))

# CHECK IF INPUT IS VALID COMMAND
# ------------------------------------------------------------------------------
isCommand() {
    command -v "$1" >/dev/null 2>&1
}

# CLEAN UP AFTER COMPLETED OR FAILED INSTALLATION
# ------------------------------------------------------------------------------
cleanUp() {
    rm -f pythonCommand errorLog moduleList
}

# UPDATE LOCAL PACKAGES USING apt-get update
# ------------------------------------------------------------------------------
updatePackages() {

    # Update local package cache. Return error if cache cannot be updated
    local str="Checking for updated packages"
    printf "  %b %s..." "${INFO}" "${str}"
    if (sudo ${PKG_UPDATE_CACHE} &> errorLog); then

        # Alert user if there are updates to install
        updatesToInstall=$(eval ${PKG_UPDATE_COUNT})
        if [[ "$updatesToInstall" -gt "0" ]]; then
            printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
            if [[ "$updatesToInstall" -eq "1" ]]; then
                local str="$updatesToInstall updated package available. Use 'sudo apt upgrade' to install"
            else
                local str="$updatesToInstall updated packages available. Use 'sudo apt upgrade' to install"
            fi
            printf "  %b %s\\n" "${INFO}" "${str}"
        else
            printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
            local str="No updated packages found"
            printf "  %b %s\\n" "${INFO}" "${str}"
        fi
    else
        printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
        printf "  %bError: Unable to update local package cache. Please check your internet connection\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<errorLog)"
        cleanUp
        exit 1
    fi
}

# INSTALL PACKAGES REQUIRED BY THE WeatherFlow PiConsole
# ------------------------------------------------------------------------------
installPackages() {

    # Parse function input and print progress to screen
    printf "\\n  %b WeatherFlow PiConsole dependency checks...\\n" "${INFO}"
    declare -a argArray=("${WFPICONSOLE_DEPENDENCIES[@]}")
    declare -a installArray

    # Check if any of the dependent packages are already installed.
    for i in "${argArray[@]}"; do
        printf "  %b Checking for %s..." "${INFO}" "${i}"
        if dpkg-query -W -f='${Status}' "${i}" 2>/dev/null | grep "ok installed" &> /dev/null; then
            printf "%b  %b Checking for %s\\n" "${OVER}" "${TICK}" "${i}"
        else
            echo -e "${OVER}  ${INFO} Checking for $i (will be installed)"
            installArray+=("${i}")
        fi
    done
    # Only install dependent packages that are missing from the system to avoid
    # unecessary downloading
    if [[ "${#installArray[@]}" -gt 0 ]]; then
        if ! (sudo debconf-apt-progress --logfile errorLog -- "${PKG_NEW_INSTALL[@]}" "${installArray[@]}"); then
            printf "  %b\\nError: Unable to install dependent packages\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
            printf "%s\\n\\n" "$(<errorLog)"
            cleanUp
            exit 1
        fi
    fi
}

# UPDATE PYTHON PACKAGE MANAGER: PIP
# ------------------------------------------------------------------------------
updatePip() {
    local str="Updating Python package manager"
    printf "\\n  %b %s..." "${INFO}" "${str}"
    if (${PIP_UPDATE} pip setuptools &> errorLog); then
        printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
    else
        printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
        printf "  %bError: Unable to update Python package manager: pip\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<errorLog)"
        cleanUp
        exit 1
    fi
}

# INSTALL PYTHON MODULES FOR THE WeatherFlow PiConsole
# ------------------------------------------------------------------------------
installPythonModules() {

    # Parse function input and print progress to screen.
    printf "\\n  %b Installing WeatherFlow PiConsole Python modules..." "${INFO}"
    declare -a argArray=("${PYTHON_MODULES[@]}")
    declare -a installArray

    # Update Python package manager: pip
    updatePip

    # Install required Python modules
    for i in "${argArray[@]}"; do
        Module=$(echo $i | cut -d"[" -f 1 | cut -d"=" -f 1)
        local str="Installing Python module"
        printf "  %b %s %s..." "${INFO}" "${str}" "${Module}"
        if (${PIP_INSTALL} "$i" &> errorLog); then
            printf "%b  %b %s %s\\n" "${OVER}" "${TICK}" "${str}" "${Module}"
        else
            printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
            printf "  %bError: Unable to install Python module: $Module\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
            printf "%s\\n\\n" "$(<errorLog)"
            cleanUp
            exit 1
        fi
    done
}

# UPDATE PYTHON MODULES FOR THE WeatherFlow PiConsole
# ------------------------------------------------------------------------------
updatePythonModules() {

    # Parse function input and print progress to screen.
    printf "\\n  %b Updating WeatherFlow PiConsole Python modules..." "${INFO}"
    declare -a argArray=("${PYTHON_MODULES[@]}")

    # Update Python package manager: pip
    updatePip

    # Get list of installed packages and versions
    python3 -m pip freeze > moduleList

    # Update required Python modules
    for i in "${argArray[@]}"; do
        Module=$(echo $i | cut -d"[" -f 1 | cut -d"=" -f 1)
        reqVer=$(echo $i | cut -d"=" -f 3)
        if grep -iF $Module moduleList &> /dev/null; then
            curVer=$(grep -iF $Module moduleList | cut -d"=" -f 3)
            if [[ "$curVer" != "$reqVer" ]]; then
                local str="Updating Python module"
                printf "  %b %s %s..." "${INFO}" "${str}" "${Module}"
                if (${PIP_INSTALL} "$i" &> errorLog); then
                    printf "%b  %b %s %s\\n" "${OVER}" "${TICK}" "${str}" "${Module}"
                else
                    printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
                    printf "  %bError: Unable to update Python module: $Module\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
                    printf "%s\\n\\n" "$(<errorLog)"
                    cleanUp
                    exit 1
                fi
            fi
        else
            local str="Installing new Python module"
            printf "  %b %s %s..." "${INFO}" "${str}" "${Module}"
            if (${PIP_INSTALL} "$i" &> errorLog); then
                printf "%b  %b %s %s\\n" "${OVER}" "${TICK}" "${str}" "${Module}"
            else
                printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
                printf "  %bError: Unable to install Python module: $Module\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
                printf "%s\\n\\n" "$(<errorLog)"
                cleanUp
                exit 1
            fi
        fi
    done
}

# INSTALL PACKAGES REQUIRED BY KIVY PYTHON LIBRARY ON ARM MACHINES
# ------------------------------------------------------------------------------
installKivyPackages() {

    # Define required packages and print progress to screen
    printf "\\n  %b Kivy Python library dependency checks...\\n" "${INFO}"
    if [[ "$PROCESSOR" = "arm"* ]]; then
        declare -a argArray=("${KIVY_DEPENDENCIES_ARM[@]}")
    else
        declare -a argArray=("${KIVY_DEPENDENCIES[@]}")
    fi
    declare -a installArray

    # Check if any of the required packages are already installed.
    for i in "${argArray[@]}"; do
        printf "  %b Checking for %s..." "${INFO}" "${i}"
        if dpkg-query -W -f='${Status}' "${i}" 2>/dev/null | grep "ok installed" &> /dev/null; then
            printf "%b  %b Checking for %s\\n" "${OVER}" "${TICK}" "${i}"
        else
            echo -e "${OVER}  ${INFO} Checking for $i (will be installed)"
            installArray+=("${i}")
        fi
    done

    # Only install required packages that are missing from the system to avoid
    # unecessary downloading
    if [[ "${#installArray[@]}" -gt 0 ]]; then
        if ! (sudo debconf-apt-progress --logfile errorLog -- "${PKG_NEW_INSTALL[@]}" "${installArray[@]}"); then
            printf "  %b\\nError: Unable to install dependent packages\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
            printf "%s\\n\\n" "$(<errorLog)"
            cleanUp
            exit 1
        fi
    fi
}

# INSTALL KIVY PYTHON LIBRARY
# ------------------------------------------------------------------------------
installKivy() {

    # Check if required Kivy version is installed
    local str="Kivy Python library installation check"
    printf "\\n  %b %s..." "${INFO}" "${str}"
    if python3 -c "import kivy" &> /dev/null; then
        kivyVersion=$(python3 -m pip show kivy | grep Version | cut -d" " -f2)
        if [[ "$KIVY_VERSION" == "$kivyVersion" ]]; then
            printf "%b  %b %s \\n" "${OVER}" "${TICK}" "${str}"
        else
            printf "%b  %b %s (will be updated)" "${OVER}" "${INFO}" "${str}"
            local updateKivy=true
        fi
    else
        printf "%b  %b %s (will be installed)" "${OVER}" "${INFO}" "${str}"
        local installKivy=true
    fi

    # Install Kivy Python library
    if [[ "$updateKivy" = true ]] || [[ "$installKivy" = true ]]; then
        if [[ "$updateKivy" = true ]]; then
            local str="Updating Kivy Python library"
        else
            local str="Installing Kivy Python library"
        fi
        printf "\\n  %b %s..." "${INFO}" "${str}"
        if ($PIP_INSTALL $KIVY_REPO &> errorLog); then
            printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
        else
            printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
            printf "  %bError: Unable to install Kivy Python library\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
            printf "%s\\n\\n" "$(<errorLog)"
            cleanUp
            exit 1
        fi

        # Update Kivy configuration
        updateKivyConfig
    fi
}

# UPDATE KIVY CONFIGURATION
# ------------------------------------------------------------------------------
updateKivyConfig() {

    # Create Kivy config file for user that called function
    local str="Updating Kivy configuration for touch screen"
    printf "  %b %s..." "${INFO}" "${str}"
    if python3 -c "import kivy" &> errorLog; then
        :
    else
        printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
        printf "  %bError: Unable to update Kivy configuration for touch screen\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<errorLog)"
        cleanUp
        exit 1
    fi

    # Ensure current user is in input and video groups
    sudo usermod -a -G input,video $USER

    # Echo Python commands to file required to modify the Kivy config for the
    # Raspberry Pi touchscreen
    configFile=$(eval echo "~$USER/.kivy/config.ini")
    echo "import configparser" >> pythonCommand
    echo "Config = configparser.ConfigParser()" >> pythonCommand
    echo "Config.read('$configFile')" >> pythonCommand
    echo "Config.remove_section('input')" >> pythonCommand
    echo "Config.add_section('input')" >> pythonCommand
    echo "Config.set('input','mouse','mouse')" >> pythonCommand
    echo "Config.set('input','mtdev_%(name)s','probesysfs,provider=mtdev')" >> pythonCommand
    echo "Config.set('input','hid_%(name)s','probesysfs,provider=hidinput')" >> pythonCommand
    echo "with open('$configFile','w') as configfile:" >> pythonCommand
    echo "    Config.write(configfile)" >> pythonCommand
    echo "configfile.close()" >> pythonCommand

    # Run Python command to modify Kivy config for the Raspberry Pi touchscreen
    if (python3 pythonCommand &> errorLog); then
        printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
    else
        printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
        printf "  %bError: Unable to update Kivy configuration for touch screen\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<errorLog)"
        cleanUp
        exit 1
    fi
}

# GET THE LATEST VERSION OF THE WeatherFlow PiConsole CODE FROM GITHUB
# ------------------------------------------------------------------------------
getLatestVersion() {

    # Get info on latest version from Github API and extract latest version
    # number using Python JSON tools
    gitInfo=$(curl -s $WFPICONSOLE_RELEASES -H 'Accept:application/vnd.github.v3+json')
    latestVer=$(echo $gitInfo | jq -r '.tag_name')

    # If the WeatherFlow PiConsole is already installed, get the current
    # installed version from wfpiconsole.ini file.
    if [[ -f $CONSOLEDIR/wfpiconsole.ini ]]; then
        currentVer=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$CONSOLEDIR/wfpiconsole.ini'); print(c['System']['Version'])")
        printf "\\n  %b Latest version of WeatherFlow PiConsole: %s" "${INFO}" "${latestVer}"
        printf "\\n  %b Installed version of WeatherFlow PiConsole: %s" "${INFO}" "${currentVer}"

        # Compare current version with latest version. If verions match, there
        # is no need to get the latest version
        if [[ "$currentVer" == "$latestVer" ]]; then
            printf "\\n  %b Versions match: %bNo update required%b\n" "${TICK}" "${COL_LIGHT_GREEN}" "${COL_NC}"
            return

        # Else, get the latest version of the WeatherFlow PiConsole and install
        else
            local str="Updating WeatherFlow PiConsole to ${COL_LIGHT_GREEN}${latestVer}${COL_NC}"
            printf "\\n\\n  %b %b..." "${INFO}" "${str}"
            curl -sL $WFPICONSOLE_MAIN --create-dirs -o $DLDIR/wfpiconsole.tar.gz
            installLatestVersion
        fi

    # Else, the WeatherFlow PiConsole is not installed so get the latest stable
    # version and install
    else
        local str="Installing the latest version of WeatherFlow PiConsole: ${COL_LIGHT_GREEN}${latestVer}${COL_NC}"
        printf "\\n  %b %b..." "${INFO}" "${str}"
        curl -sL $WFPICONSOLE_MAIN --create-dirs -o $DLDIR/wfpiconsole.tar.gz
        installLatestVersion
    fi
}

# GET THE LATEST PATCH FOR THE WeatherFlow PiConsole FROM GITHUB
# ------------------------------------------------------------------------------
getLatestPatch() {

    # Get info on latest patch from Github API and extract latest version
    # number using jq JSON tools
    patchInfo=$(curl -s $WFPICONSOLE_TAGS -H 'Accept: application/vnd.github.v3+json')
    patchVer=$(echo $patchInfo | jq -r '.[0].name')

    # Download latest stable patch for the WeatherFlow PiConsole and install
    local str="Patching ${COL_LIGHT_GREEN}${patchVer}${COL_NC} of the WeatherFlow PiConsole"
    printf "  %b %b..." "${INFO}" "${str}"
    curl -sL $WFPICONSOLE_MAIN --create-dirs -o $DLDIR/wfpiconsole.tar.gz
    installLatestVersion
}

# GET THE LATEST BETA VERSION FOR THE WeatherFlow PiConsole FROM GITHUB
# ------------------------------------------------------------------------------
getLatestBeta() {

    # Get info on latest patch from Github API and extract latest version
    # number using jq JSON tools
    patchInfo=$(curl -s $WFPICONSOLE_TAGS -H 'Accept: application/vnd.github.v3+json')
    patchVer=$(echo $patchInfo | jq -r '.[0].name')

    # Download latest stable beta version for the WeatherFlow PiConsole and
    # install
    local str="Installing the latest beta version of WeatherFlow PiConsole"
    printf "\\n  %b %b..." "${INFO}" "${str}"
    curl -sL $WFPICONSOLE_BETA --create-dirs -o $DLDIR/wfpiconsole.tar.gz
    installLatestVersion
}

# INSTALL THE LATEST VERSION OF THE WeatherFlow PiConsole
# ------------------------------------------------------------------------------
installLatestVersion() {

    # Extract the latest version of the WeatherFlow PiConsole from the Github
    # tarball to the temporary download folder
    tar -zxf $DLDIR/wfpiconsole.tar.gz -C $DLDIR --strip 1
    rm $DLDIR/wfpiconsole.tar.gz

    # Rsync the files in the download folder to the console directory. Delete
    # any files that have been removed in the latest version
    if (rsync -a --exclude '*.ini' --delete-after $DLDIR $CONSOLEDIR &> errorLog); then
        printf "%b  %b %b\\n" "${OVER}" "${TICK}" "${str}"
    else
        printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}" "${COL_LIGHT_GREEN}" "${COL_NC}"
        printf "  %bError: Unable to install the WeatherFlow PiConsole\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<errorLog)"
        cleanUp
        exit 1
    fi

    # Ensure console directory is owned by the correct user
    consoleOwner=$(stat -c "%U" $CONSOLEDIR)
    if [[ "$consoleOwner" != "$USER" ]]; then
        sudo chown -fR $USER $CONSOLEDIR
        sudo chgrp -fR $USER $CONSOLEDIR
    fi

    # Make sure wfpiconsole.sh file is executable and create symlink to
    # usr/bin/local so function can be called directly from the command line
    chmod 744 $CONSOLEDIR/wfpiconsole.sh
    sudo ln -sf $CONSOLEDIR/wfpiconsole.sh /usr/local/bin/wfpiconsole
}

# INSTALL THE wfpiconsole.service FILE TO /etc/systemd/system/
# ------------------------------------------------------------------------------
installServiceFile () {

    # Write current user and install directory to wfpiconsole.service file
    sed -i "s+WorkingDirectory=.*$+WorkingDirectory=$CONSOLEDIR+" $CONSOLEDIR/wfpiconsole.service
    sed -i "s+User=.*$+User=$USER+" $CONSOLEDIR/wfpiconsole.service
    sed -i "s+StandardOutput=.*$+StandardOutput=file:${CONSOLEDIR}wfpiconsole.log+" $CONSOLEDIR/wfpiconsole.service
    sed -i "s+StandardError=.*$+StandardError=file:${CONSOLEDIR}wfpiconsole.log+" $CONSOLEDIR/wfpiconsole.service

    # Install wfpiconsole.service file to /etc/systemd/system/ and reload deamon
    local str="Copying service file to autostart directory"
    printf "  %b %s..." "${INFO}" "${str}"
    sudo cp $CONSOLEDIR/wfpiconsole.service /etc/systemd/system/
    if (sudo systemctl daemon-reload &> errorLog); then
        printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
    else
        printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
        printf "  %bError: Unable to install wfpiconsole.service file\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<errorLog)"
        cleanUp
        exit 1
    fi
}

# ENABLE THE wfpiconsole.service
# ------------------------------------------------------------------------------
enableService () {

    # Enable wfpiconsole.service file
    local str="Enabling the WeatherFlow PiConsole service file"
    printf "  %b %s..." "${INFO}" "${str}"
    rm -f wfpiconsole.log
    if (sudo systemctl enable wfpiconsole &> errorLog); then
        if (sudo systemctl start wfpiconsole &> errorLog); then
            printf "%b  %b %s\\n\\n" "${OVER}" "${TICK}" "${str}"
        else
            printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
            printf "  %bError: Unable to enable the WeatherFlow PiConsole service file\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
            printf "%s\\n\\n" "$(<errorLog)"
            cleanUp
            exit 1
        fi
    else
        printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
        printf "  %bError: Unable to enable the WeatherFlow PiConsole service file\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<errorLog)"
        cleanUp
        exit 1
    fi
}

# DISABLE THE wfpiconsole.service
# ------------------------------------------------------------------------------
disableService () {

    # Disable the wfpiconsole service
    local str="Disabling the WeatherFlow PiConsole service file"
    printf "  %b %s..." "${INFO}" "${str}"
    if (sudo systemctl disable wfpiconsole.service &> errorLog); then
        printf "%b  %b %s\\n\\n" "${OVER}" "${TICK}" "${str}"
    else
        printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
        printf "  %bError: Unable to disable the WeatherFlow PiConsole service file\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<errorLog)"
        cleanUp
        exit 1
    fi
}

# DISPLAY REQUIRED PROCESS STARTING DIALOGUE
# ------------------------------------------------------------------------------
processStarting() {

    # Display installation starting dialogue
    case $1 in
        install)
            whiptail --msgbox --backtitle "Welcome" --title "WeatherFlow PiConsole automated installer" \
            "\\n\\nThanks for checking out the WeatherFlow PiConsole. This script will guide you through the installation process on your Raspberry Pi." ${r} ${c}
            printf "\\n"
            printf "  ================================ \\n"
            printf "  Installing WeatherFlow PiConsole \\n"
            printf "  ================================ \\n\\n"
            ;;
    # Display update starting dialogue
        runUpdate)
            printf "\\n"
            printf "  ============================== \\n"
            printf "  Updating WeatherFlow PiConsole \\n"
            printf "  ============================== \\n\\n"
            ;;
    # Display patch starting dialogue
        patch)
            printf "\\n"
            printf "  ============================== \\n"
            printf "  Patching WeatherFlow PiConsole \\n"
            printf "  ============================== \\n\\n"
            ;;
    # Display update starting dialogue
        runBeta)
            printf "\\n"
            printf "  ===================================================== \\n"
            printf "  Updating WeatherFlow PiConsole to latest beta version \\n"
            printf "  ===================================================== \\n\\n"
            ;;
    # Display autostart-enable starting dialogue
        autostart-enable)
            printf "\\n"
            printf "  ====================================== \\n"
            printf "  Enabling console autostart during boot \\n"
            printf "  ====================================== \\n\\n"
            ;;
    # Display autostart-disable starting dialogue
        autostart-disable)
            printf "\\n"
            printf "  ======================================= \\n"
            printf "  Disabling console autostart during boot \\n"
            printf "  ======================================= \\n\\n"
    esac
}

# DISPLAY REQUIRED PROCESS COMPLETE DIALOGUE
# ------------------------------------------------------------------------------
processComplete() {

    # Display installation complete dialogue
    case $1 in
        install)
            printf "  \\n"
            printf "  ============================================ \\n"
            printf "  WeatherFlow PiConsole installation complete! \\n"
            printf "  Start the console with: 'wfpiconsole start'  \\n"
            printf "  ============================================ \\n\\n"
            ;;
    # Display update complete dialogue
        runUpdate)
            printf "  \\n"
            printf "  ============================================= \\n"
            printf "  WeatherFlow PiConsole update complete!        \\n"
            printf "  Restart the console with: 'wfpiconsole start' \\n"
            printf "  or 'wfpiconsole autostart-enable'             \\n"
            printf "  ============================================= \\n\\n"
            ;;
    # Display patch complete dialogue
        patch)
            printf "  \\n"
            printf "  ============================================= \\n"
            printf "  WeatherFlow PiConsole patching complete!      \\n"
            printf "  Restart the console with: 'wfpiconsole start' \\n"
            printf "  or 'wfpiconsole autostart-enable'             \\n"
            printf "  ============================================= \\n\\n"
            ;;
    # Display beta complete dialogue
        runBeta)
            printf "  \\n"
            printf "  ============================================= \\n"
            printf "  WeatherFlow PiConsole beta update complete!   \\n"
            printf "  Restart the console with: 'wfpiconsole start' \\n"
            printf "  or 'wfpiconsole autostart-enable'             \\n"
            printf "  ============================================= \\n\\n"
            ;;
    # Display autostart-enable complete dialogue
        autostart-enable)
            printf "  ==================================================== \\n"
            printf "  WeatherFlow PiConsole autostart sucesfully enabled   \\n"
            printf "  Console will now start automatically at boot up      \\n"
            printf "  Starting console for current session. Please wait... \\n"
            printf "  ==================================================== \\n\\n"
            ;;
    # Display autostart-disable complete dialogue
        autostart-disable)
            printf "  =================================================== \\n"
            printf "  WeatherFlow PiConsole autostart sucesfully disabled \\n"
            printf "  Use 'wfpiconsole stop' to halt current session      \\n"
            printf "  =================================================== \\n\\n"
    esac
}

# START THE WeatherFlow PiConsole
# ------------------------------------------------------------------------------
start () {
    cd $CONSOLEDIR && rm -f wfpiconsole.log
    python3 main.py |& tee wfpiconsole.log
}

# STOP THE WeatherFlow PiConsole
# ------------------------------------------------------------------------------
stop () {
    if (sudo systemctl | grep wfpiconsole.service &> errorLog); then
        sudo systemctl stop wfpiconsole.service
    else
        pkill -HUP -f main.py
    fi
    cleanUp
}

# INSTALL WeatherFlow PiConsole
# ------------------------------------------------------------------------------
install() {

    # Display installation starting dialogue
    processStarting ${FUNCNAME[0]}
    # Check for and ask user if they wish to install any updated local packages
    updatePackages
    # Install required packages
    installPackages
    # Install required Python modules
    installPythonModules
    # Install required Kivy dependencies
    installKivyPackages
    # Install Kivy Python library
    installKivy
    # Get the latest version of the WeatherFlow PiConsole and install
    getLatestVersion
    # Clean up after update
    cleanUp
    # Display installation complete dialogue
    processComplete ${FUNCNAME[0]}
}

# UPDATE WeatherFlow PiConsole TO THE LATEST STABLE VERSION
# ------------------------------------------------------------------------------
update() {

    # Fetch the latest update code directly from the master Github branch. This
    # ensures that changes in dependencies are addressed during this update
    curl -sSL $WFPICONSOLE_MAIN_UPDATE | bash -s runUpdate
}

# RUN THE STABLE VERSION UPDATE PROCESS
# ------------------------------------------------------------------------------
runUpdate() {

    # Display installation starting dialogue
    processStarting ${FUNCNAME[0]}
    # Check for and ask user if they wish to install any updated local packages
    updatePackages
    # Check if any new dependencies are required
    installPackages
    # Update Python modules as required
    updatePythonModules
    # Install required Kivy dependencies
    installKivyPackages
    # Install Kivy Python library
    installKivy
    # Get the latest version of the WeatherFlow PiConsole and install
    getLatestVersion
    # Clean up after installation
    cleanUp
    # Display update complete dialogue
    processComplete ${FUNCNAME[0]}
}

# PATCH THE WeatherFlow PiConsole WITH THE LATEST STABLE CHANGES
# ------------------------------------------------------------------------------
patch() {

    # Display installation starting dialogue
    processStarting ${FUNCNAME[0]}
    # Get the latest patch for the WeatherFlow PiConsole and install
    getLatestPatch
    # Clean up after installation
    cleanUp
    # Display update complete dialogue
    processComplete ${FUNCNAME[0]}
}

# UPDATE WeatherFlow PiConsole TO THE LATEST STABLE BETA VERSION
# ------------------------------------------------------------------------------
beta() {

    # Fetch the latest beta update code directly from the develop Github branch.
    # This ensures that changes in dependencies are addressed during this update
    curl -sSL $WFPICONSOLE_BETA_UPDATE | bash -s runBeta
}

# RUN THE BETA VERSION UPDATE PROCESS
# ------------------------------------------------------------------------------
runBeta() {

    # Display installation starting dialogue
    processStarting ${FUNCNAME[0]}
    # Check for and ask user if they wish to install any updated local packages
    updatePackages
    # Check if any new dependencies are required
    installPackages
    # Update Python modules as required
    updatePythonModules
    # Install required Kivy dependencies
    installKivyPackages
    # Install Kivy Python library
    installKivy
    # Get the latest patch for the WeatherFlow PiConsole and install
    getLatestBeta
    # Clean up after installation
    cleanUp
    # Display update complete dialogue
    processComplete ${FUNCNAME[0]}
}

# SET THE WeatherFlow PiConsole TO START AUTOMATICALLY
# ------------------------------------------------------------------------------
autostart-enable () {

    # Display autostart-enable starting dialogue
    processStarting ${FUNCNAME[0]}
    # Edit and install wfpiconsole.service file
    installServiceFile
    # Enable wfpiconsole service
    enableService
    # Clean up after enabling autostart
    cleanUp
    # Display autostart-enable complete dialogue
    processComplete ${FUNCNAME[0]}
}

# DISABLE THE WeatherFlow PiConsole FROM STARTING AUTOMATICALLY
# ------------------------------------------------------------------------------
autostart-disable () {

    # Display autostart-disable starting dialogue
    processStarting ${FUNCNAME[0]}
    # Disable wfpiconsole service
    disableService
    # Clean up after disabling autostart
    cleanUp
    # Display autostart-disable complete dialogue
    processComplete ${FUNCNAME[0]}
}

# SCRIPT USAGE
# ------------------------------------------------------------------------------
helpFunc() {
  echo "Usage: wfpiconsole [options]
Example: 'wfpiconsole update'

Options:
  start                 : Start the WeatherFlow PiConsole
  stop                  : Stop the WeatherFlow PiConsole
  install               : Install the WeatherFlow PiConsole
  update                : Update the WeatherFlow PiConsole
  patch                 : Patch the WeatherFlow PiConsole
  autostart-enable      : Set the WeatherFlow PiConsole to autostart at boot
  autostart-disable     : Stop the WeatherFlow PiConsole autostarting at boot"
  exit 0
}

# SCRIPT CALLED WITH NO ARGUMENTS. PRINT HELP FUNCTION
# ------------------------------------------------------------------------------
if [ $# -eq 0 ]; then
    printf "Unrecognised usage\\n"
    helpFunc
fi

# ENSURE ROOT ACCESS IS AVAILABLE
# ------------------------------------------------------------------------------
# Ensure sudo command is available and script can be elevated to root privileges
if [[ ! -x "$(command -v sudo)" ]]; then
    printf "\\n"
    printf "  %bError: Unable to $1 the WeatherFlow PiConsole.\\n\\n%b" "${COL_LIGHT_RED}" "${COL_NC}"
    printf "  sudo is needed to $1 the WeatherFlow PiConsole\\n"
    printf "  Please install sudo and run this script again Pi\\n\\n"
    cleanUp
    exit 1
fi
if [[ "${1}" != "start" ]]; then
    if (sudo true); then
        if [[ "${1}" != "stop" ]] && [[ "${1}" != "update" ]] && [[ "${1}" != "beta" ]]; then
            printf "\\n  %b Root user check passed\\n" "${TICK}"
        fi
    else
        printf "\\n %b  %b Root user check failed\\n" "${OVER}" "${CROSS}"
        printf "  %bError: Unable to ${1} the WeatherFlow PiConsole \\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "\\n"
        cleanUp
        exit 1
    fi
fi

# CHECK OS/HARDWARE AND ADD REQUIRED REPOSITORIES WHEN INSTALL OR UPDATING
# ------------------------------------------------------------------------------
if [[ "${1}" == "install" ]] || [[ "${1}" == "runUpdate" ]] || [[ "${1}" == "runBeta" ]] || [[ "${1}" == "patch" ]] ; then

    # Check compatability of hardware/OS
    PROCESSOR=$(uname -m)
    if [[ $PROCESSOR = arm* ]] || [[ $PROCESSOR = x86_64 ]] || [[ $PROCESSOR = i*86 ]] || [[ $PROCESSOR = aarch64 ]]; then
        printf "  %b Hardware check passed (%b)\\n" "${TICK}" "${PROCESSOR}"
    else
        printf "  %b Hardware check failed (%b)\\n\\n" "${CROSS}" "${PROCESSOR}"
        cleanUp
        exit 1
    fi
    OS=$(. /etc/os-release && echo $PRETTY_NAME)
    if isCommand apt-get ; then
        printf "  %b OS check passed (%b)\\n" "${TICK}" "${OS}"
    else
        printf "  %b OS check failed (%b)\\n\\n" "${CROSS}" "${OS}"
        cleanUp
        exit 1
    fi

    # Add "universe" repository when running Ubtuntu if required
    if echo $OS | grep -iF "Ubuntu" &> /dev/null; then
        if ! (find /etc/apt/ -name *.list | xargs cat | grep universe &> /dev/null); then
            str="Enabling Universe repository in Ubuntu"
            printf "  %b %s..." "${INFO}" "${str}"
            if (sudo add-apt-repository universe &> errorLog); then
                printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
            else
                printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
                printf "  %bError: Unable to enabling Universe repository.\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
                printf "%s\\n\\n" "$(<errorLog)"
                cleanUp
                exit 1
            fi
        fi
    fi
fi

# HANDLE REDIRECTING TO SPECIFIC FUNCTIONS BASED ON INPUT ARGUMENTS
# ------------------------------------------------------------------------------
case "${1}" in
    "start"               ) start;;
    "stop"                ) stop;;
    "install"             ) install;;
    "update"              ) update;;
    "patch"               ) patch;;
    "beta"                ) beta;;
    "runUpdate"           ) runUpdate;;
    "runBeta"             ) runBeta;;
    "autostart-enable"    ) autostart-enable;;
    "autostart-disable"   ) autostart-disable;;
    *                     ) printf "Unrecognised usage\\n" && helpFunc;;
esac
