#!/usr/bin/env bash

# Automated installer and updater for the WeatherFlow PiConsole. Modified
# heavily from the PiHole and PiVPN installers.
# Copyright (C) 2018-2020 Peter Davis

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
CONSOLEDIR=/home/${USER}/wfpiconsole/
DLDIR=${CONSOLEDIR}/temp/
PKG_MANAGER="apt-get"
PKG_UPDATE_CACHE="${PKG_MANAGER} update"
PKG_UPDATE_INSTALL="${PKG_MANAGER} dist-upgrade -y"
PKG_UPDATE_COUNT="${PKG_MANAGER} -s -o Debug::NoLocking=true upgrade | grep -c ^Inst || true"
PKG_NEW_INSTALL=(${PKG_MANAGER} --yes install)
PKG_DEPENDENCIES=(libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev
                  pkg-config libgl1-mesa-dev libgles2-mesa-dev python-setuptools
                  libgstreamer1.0-dev git gstreamer1.0-plugins-{bad,base,good,ugly}
                  python-dev libmtdev-dev xclip xsel libatlas-base-dev gstreamer1.0-{omx,alsa}
                  rng-tools build-essential libssl-dev libjpeg-dev libffi6 libffi-dev jq)
PYTHON_MODS=(autobahn[twisted] numpy pytz pyasn1-modules service_identity geopy ephem pillow packaging)
CYTHON_VERSION="0.29.10"
KIVY_VERSION="1.11.1"
KIVY_REPO="https://github.com/kivy/kivy/archive/"$KIVY_VERSION".zip"
WFPICONSOLE_PATCH="https://github.com/peted-davis/WeatherFlow_PiConsole/tarball/master"
WFPICONSOLE_UPDATE="https://raw.githubusercontent.com/peted-davis/WeatherFlow_PiConsole/master/wfpiconsole.sh"

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
    rm -f pythonCommand errorLog
}

# CHECK COMPATABILITY OF SYSTEM FOR RUNNING THE WEATHERFLOW PICONSOLE
# ------------------------------------------------------------------------------
hardwareCheck() {

    # Ensure installer is running on a Raspberry Pi
    local Processor=$(uname -m)
    if [[ "$Processor" = "arm"* ]]; then
        printf "  %b Raspberry Pi found. Hardware check passed\\n" "${TICK}"
        if isCommand apt-get ; then
            printf "  %b Raspbian (Debian) found. OS check passed\\n" "${TICK}"
        else
            printf "  %b Raspbian (Debian) not found. OS check failed\\n\\n" "${CROSS}"
            cleanUp
            exit 1
        fi
    else
        printf "  %b Raspberry Pi not found. Hardware check failed\\n" "${CROSS}"
        cleanUp
        exit 1
    fi
}

# UPDATE LOCAL PACKAGES USING apt-get update AND apt-get upgrade
# ------------------------------------------------------------------------------
updatePackages() {

    # Update local package cache. Return error if cache cannot be updated
    local str="Checking for updated packages"
    printf "  %b %s..." "${INFO}" "${str}"
    if (sudo ${PKG_UPDATE_CACHE} &> errorLog); then

        # If there are updates to install, check if user wishes to apply updates
        updatesToInstall=$(eval ${PKG_UPDATE_COUNT})
        if [ "$updatesToInstall" -gt "0" ]; then
            backtitle="Installing updated packages"
            title="Updated packages available to install"
            if [ "$updatesToInstall" -eq "1" ]; then
                msg="OPTIONAL: There is $updatesToInstall updated package to install. Do you wish to install it? This step is not required, but is highly recommended to keep your Raspberry Pi up-to-date and secure"
            else
                msg="OPTIONAL: There are $updatesToInstall updated packages to install. Do you wish to install them? This step is not required, but is highly recommended to keep your Raspberry Pi up-to-date and secure"
            fi
            if (whiptail --backtitle "$backtitle" --title "$title" --yesno --defaultno "$msg" ${r} ${c}); then

                # Apply updates using apt-get. Return error if updates cannot be
                #installed
                printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
                local str="Installing updated packages"
                printf "  %b %s..." "${INFO}" "${str}"
                if (sudo debconf-apt-progress --logfile errorLog -- ${PKG_UPDATE_INSTALL}); then
                    printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
                else
                    printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
                    printf "  %bError: Unable to install package updates.\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
                    printf "%s\\n\\n" "$(<errorLog)"
                    cleanUp
                    exit 1
                fi
            else
                printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
                local str="Updated packages not installed. It is recommended to update your OS after the installation has finished"
                printf "  %b %s\\n" "${CROSS}" "${str}"
            fi
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
    declare -a argArray=("${!1}")
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
    if (python3 -m pip install --user --upgrade pip setuptools &> errorLog); then
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
    printf "\\n  %b WeatherFlow PiConsole Python module checks..." "${INFO}"
    declare -a argArray=("${!1}")
    declare -a installArray

    # Update Python package manager: pip
    updatePip

    # Get list of installed Python modules
    PythonList=`python3 -m pip list`

    # Check if any of the dependent Python modules are already installed.
    for i in "${argArray[@]}"; do
        Module=`echo $i | cut -d"[" -f 1 | cut -d"=" -f 1`
        local str="Checking for Python module"
        printf "  %b %s %s..." "${INFO}" "${str}" "${Module}"
        if echo $PythonList | grep -iF $Module &> /dev/null; then
            printf "%b  %b %s %s\\n" "${OVER}" "${TICK}" "${str}" "${i}"
        else
            if python3 -c "import ${i%[*}" &> /dev/null; then
                printf "%b  %b %s %s\\n" "${OVER}" "${TICK}" "${str}" "${i}"
            else
                printf "%b  %b %s %s (will be installed)\\n" "${OVER}" "${INFO}" "${str}" "${i}"
                installArray+=("${i}")
            fi
        fi
    done

    # Check if required Cython version is installed
    local str="Checking for Python module cython"
    printf "  %b %s %s..." "${INFO}" "${str}" "${Module}"
    if echo $PythonList | grep -iF Cython &> /dev/null; then
        cythonVersion=`echo $PythonList | sed -n 's/.*Cython //p' | cut -d" " -f 1`
        if [ "$CYTHON_VERSION" == "$cythonVersion" ]; then
            printf "%b  %b %s \\n" "${OVER}" "${TICK}" "${str}"
        else
            printf "%b  %b %s (will be installed)\\n" "${OVER}" "${INFO}" "${str}"
            local requireCython=true
        fi
    else
        printf "%b  %b %s (will be installed)\\n" "${OVER}" "${INFO}" "${str}"
        local requireCython=true
    fi

    # Only install dependent Python modules that are missing from the system to
    # avoid unecessary downloading
    if [[ "${#installArray[@]}" -gt 0 ]]; then
        printf "\\n  %b Installing WeatherFlow PiConsole Python modules...\\n" "${INFO}"
        for i in "${installArray[@]}"; do
            local str="Installing Python module"
            printf "  %b %s %s..." "${INFO}" "${str}" "${i}"
            if (python3 -m pip install --user "$i" &> errorLog); then
                printf "%b  %b %s %s\\n" "${OVER}" "${TICK}" "${str}" "${i}"
            else
                printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
                printf "  %bError: Unable to install Python module: $i\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
                printf "%s\\n\\n" "$(<errorLog)"
                cleanUp
                exit 1
            fi
        done
    fi

    # Install Cython if required
    if [ "$requireCython" = true ] ; then
        installCython
    fi
}

# INSTALL CYTHON
# ------------------------------------------------------------------------------
installCython() {
    local str="Installing Python module cython"
    printf "  %b %s..." "${INFO}" "${str}"
    if (python3 -m pip install --user cython==$CYTHON_VERSION &> errorLog); then
        printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
    else
        printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
        printf "  %bError: Unable to install Python module cython\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<errorLog)"
        cleanUp
        exit 1
    fi
}

# UPDATE DEPENDENT PYTHON MODULES FOR THE WeatherFlow PiConsole
# ------------------------------------------------------------------------------
updatePythonModules() {

    # Parse function input and print progress to screen
    printf "\\n  %b Updating WeatherFlow PiConsole Python modules...\\n" "${INFO}"
    declare -a argArray=("${!1}")

    # Update outdated dependent Python modules
    for i in "${argArray[@]}"; do
        local str="Updating Python module"
        printf "  %b %s %s..." "${INFO}" "${str}" "${i}"
        if (python3 -m pip install --user --upgrade "$i" &> errorLog); then
            printf "%b  %b %s %s\\n" "${OVER}" "${TICK}" "${str}" "${i}"
        else
            printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
            printf "  %bError: Unable to update Python module: $i\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
            printf "%s\\n\\n" "$(<errorLog)"
            cleanUp
            exit 1
        fi
    done
}

# INSTALL KIVY PYTHON LIBRARY
# ------------------------------------------------------------------------------
installKivy() {
    local str="Installing Kivy Python library [This will take time - please be patient]"
    printf "\\n  %b %s..." "${INFO}" "${str}"
    if python3 -c "import kivy" &> /dev/null; then
        printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
    else
        if (python3 -m pip install --user $KIVY_REPO &> errorLog); then
            printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
        else
            printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
            printf "  %bError: Unable to install Kivy Python library\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
            printf "%s\\n\\n" "$(<errorLog)"
            cleanUp
            exit 1
        fi
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
    gitInfo=$(curl -s 'https://api.github.com/repos/peted-davis/WeatherFlow_PiConsole/releases/latest' -H 'Accept:application/vnd.github.v3+json')
    latestVer=$(echo "$gitInfo" | jq -r '.tag_name')
    tarballLoc=$(echo "$gitInfo" | jq -r '.tarball_url')

    # If the WeatherFlow PiConsole is already installed, get the current
    # installed version from wfpiconsole.ini file.
    if [ -f $CONSOLEDIR/wfpiconsole.ini ]; then
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
            curl -sL $tarballLoc --create-dirs -o $DLDIR/wfpiconsole.tar.gz
            installLatestVersion
        fi

    # Else, the WeatherFlow PiConsole is not installed so get the latest version
    # and install
    else
        local str="Installing the latest version of WeatherFlow PiConsole: ${COL_LIGHT_GREEN}${latestVer}${COL_NC}"
        printf "\\n  %b %b..." "${INFO}" "${str}"
        curl -sL $tarballLoc --create-dirs -o $DLDIR/wfpiconsole.tar.gz
        installLatestVersion
    fi
}

# GET THE LATEST PATCH FOR THE WeatherFlow PiConsole FROM GITHUB
# ------------------------------------------------------------------------------
getLatestPatch() {

    # Get info on latest patch from Github API and extract latest version
    # number using jq JSON tools
    patchInfo=$(curl -s 'https://api.github.com/repos/peted-davis/WeatherFlow_PiConsole/tags' -H 'Accept: application/vnd.github.v3+json')
    patchVer=$(echo "$patchInfo" | jq -r '.[0].name')

    # Download latest patch for the WeatherFlow PiConsole
    local str="Patching the WeatherFlow PiConsole to ${COL_LIGHT_GREEN}${patchVer}${COL_NC}"
    printf "\\n  %b %b..." "${INFO}" "${str}"
    curl -sL $WFPICONSOLE_PATCH --create-dirs -o $DLDIR/wfpiconsole.tar.gz

    # Install latest patch
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
    if [ "$consoleOwner" != "$USER" ]; then
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
    sed -i "s+StandardOutput=.*$+StandardOutput=file:$CONSOLEDIR/wfpiconsole.log+" $CONSOLEDIR/wfpiconsole.service
    sed -i "s+StandardError=.*$+StandardError=file:$CONSOLEDIR/wfpiconsole.log+" $CONSOLEDIR/wfpiconsole.service

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
            "\\n\\nThanks for checking out the WeatherFlow PiConsole. This script will guide you through the installation process on your Raspbery Pi." ${r} ${c}
            printf "\\n"
            printf "  ================================\\n"
            printf "  Installing WeatherFlow PiConsole\\n"
            printf "  ================================\\n\\n"
            ;;
    # Display update starting dialogue
        runUpdate)
            printf "\\n"
            printf "  ==============================\\n"
            printf "  Updating WeatherFlow PiConsole\\n"
            printf "  ==============================\\n\\n"
            ;;
    # Display patch starting dialogue
        patch)
            printf "\\n"
            printf "  ==============================\\n"
            printf "  Patching WeatherFlow PiConsole\\n"
            printf "  ==============================\\n\\n"
            ;;
    # Display autostart-enable starting dialogue
        autostart-enable)
            printf "\\n"
            printf "  ======================================\\n"
            printf "  Enabling console autostart during boot \\n"
            printf "  ======================================\\n\\n"
            ;;
    # Display autostart-disable starting dialogue
        autostart-disable)
            printf "\\n"
            printf "  =======================================\\n"
            printf "  Disabling console autostart during boot \\n"
            printf "  =======================================\\n\\n"
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
    # Display patch starting dialogue
        patch)
            printf "  \\n"
            printf "  ============================================= \\n"
            printf "  WeatherFlow PiConsole patching complete!      \\n"
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
}

# INSTALL WeatherFlow PiConsole
# ------------------------------------------------------------------------------
install() {

    # Display installation starting dialogue
    processStarting ${FUNCNAME[0]}
    # Check that the install command is being run on a Raspberry Pi
    hardwareCheck
    # Check for and ask user if they wish to install any updated local packages
    updatePackages
    # Install required packages
    installPackages PKG_DEPENDENCIES[@]
    # Install required Python modules
    installPythonModules PYTHON_MODS[@]
    # Install Kivy Python library
    installKivy
    # Configure Kivy for touchscreen
    updateKivyConfig
    # Get the latest version of the WeatherFlow PiConsole and install
    getLatestVersion
    # Clean up after update
    cleanUp
    # Display installation complete dialogue
    processComplete ${FUNCNAME[0]}
}

# UPDATE WeatherFlow PiConsole
# ------------------------------------------------------------------------------
update() {

    # Fetch the latest update code directly from the master Github branch. This
    # ensures that changes in dependencies are addressed during this update
    curl -sSL $WFPICONSOLE_UPDATE | bash -s runUpdate
}

# RUN THE UPDATE PROCESS
# ------------------------------------------------------------------------------
runUpdate() {

    # Display installation starting dialogue
    processStarting ${FUNCNAME[0]}
    # Check that the install command is being run on a Raspberry Pi
    hardwareCheck
    # Check for and ask user if they wish to install any updated local packages
    updatePackages
    # Check if any new dependencies are required
    installPackages PKG_DEPENDENCIES[@]
    # Check if any new Python modules are required
    installPythonModules PYTHON_MODS[@]
    # Update outdated dependent Python modules
    #updatePythonModules PYTHON_MODS[@]
    # Get the latest version of the WeatherFlow PiConsole and install
    getLatestVersion
    # Clean up after installation
    cleanUp
    # Display update complete dialogue
    processComplete ${FUNCNAME[0]}
}

# PATCH THE WeatherFlow PiConsole
# ------------------------------------------------------------------------------
patch() {

    # Display installation starting dialogue
    processStarting ${FUNCNAME[0]}
    # Check that the patch command is being run on a Raspberry Pi
    hardwareCheck
    # Check for and ask user if they wish to install any updated local packages
    updatePackages
    # Get the latest patch for the WeatherFlow PiConsole and install
    getLatestPatch
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

# ENSURE ROOT ACCESS IS AVAILABLE AND PARSE COMMAND LINE INPUTS
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
        if [[ "${1}" != "stop" ]] && [[ "${1}" != "update" ]]; then
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

# Handle redirecting to specific functions based on input arguments
case "${1}" in
    "start"               ) start;;
    "stop"                ) stop;;
    "install"             ) install;;
    "update"              ) update;;
    "patch"               ) patch;;
    "runUpdate"           ) runUpdate;;
    "autostart-enable"    ) autostart-enable;;
    "autostart-disable"   ) autostart-disable;;
    *                     ) printf "Unrecognised usage\\n" && helpFunc;;
esac
