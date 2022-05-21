#!/usr/bin/env bash

# Automated installer and updater for the WeatherFlow PiConsole. Modified
# heavily from the PiHole and PiVPN installers.
# Copyright (C) 2018-2022 Peter Davis

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
                          libssl-dev libffi-dev libatlas-base-dev jq)
KIVY_DEPENDENCIES_ARM=(pkg-config libgl1-mesa-dev libgles2-mesa-dev libgstreamer1.0-dev
                       gstreamer1.0-plugins-{bad,base,good,ugly} gstreamer1.0-{omx,alsa}
                       libmtdev-dev xclip xsel libjpeg-dev libsdl2-dev libsdl2-image-dev
                       libsdl2-mixer-dev libsdl2-ttf-dev)
KIVY_DEPENDENCIES=(ffmpeg libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev
                   libportmidi-dev libswscale-dev libavformat-dev libavcodec-dev zlib1g-dev
                   libgstreamer1.0-dev gstreamer1.0-plugins-base gstreamer1.0-plugins-good)

# Python modules and versions
KIVY_VERSION="2.0.0"
PYTHON_MODULES=(cython==0.29.26
                websockets==10.1
                numpy==1.21.4
                pytz==2021.3
                ephem==4.1.3
                packaging==21.3
                pyOpenSSL==21.0.0
                certifi==2021.10.8)

# Github repositories
KIVY_REPO="https://github.com/kivy/kivy/archive/"$KIVY_VERSION".zip"
WFPICONSOLE_REPO="https://github.com/peted-davis/WeatherFlow_PiConsole.git"
WFPICONSOLE_TAGS="https://api.github.com/repos/peted-davis/WeatherFlow_PiConsole/tags"
WFPICONSOLE_RAW="https://raw.githubusercontent.com/peted-davis/WeatherFlow_PiConsole"
WFPICONSOLE_MAIN_UPDATE=$WFPICONSOLE_RAW"/main/wfpiconsole.sh"
WFPICONSOLE_BETA_UPDATE=$WFPICONSOLE_RAW"/develop/wfpiconsole.sh"

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
is_command() {
    command -v "$1" >/dev/null 2>&1
}

# CLEAN UP AFTER COMPLETED OR FAILED INSTALLATION
# ------------------------------------------------------------------------------
clean_up() {
    rm -f python_command error_log module_list
}

# UPDATE LOCAL PACKAGES USING apt-get update
# ------------------------------------------------------------------------------
update_packages() {

    # Update local package cache. Return error if cache cannot be updated
    local str="Checking for updated packages"
    printf "  %b %s..." "${INFO}" "${str}"
    if (sudo ${PKG_UPDATE_CACHE} &> error_log); then

        # Alert user if there are updates to install
        updates_to_install=$(eval ${PKG_UPDATE_COUNT})
        if [[ "$updates_to_install" -gt "0" ]]; then
            printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
            if [[ "$updates_to_install" -eq "1" ]]; then
                local str="$updates_to_install updated package available. Use 'sudo apt upgrade' to install"
            else
                local str="$updates_to_install updated packages available. Use 'sudo apt upgrade' to install"
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
        printf "%s\\n\\n" "$(<error_log)"
        clean_up
        exit 1
    fi
}

# INSTALL PACKAGES REQUIRED BY THE WeatherFlow PiConsole
# ------------------------------------------------------------------------------
install_packages() {

    # Parse function input and print progress to screen
    printf "\\n  %b WeatherFlow PiConsole dependency checks...\\n" "${INFO}"
    declare -a arg_array=("${WFPICONSOLE_DEPENDENCIES[@]}")
    declare -a install_array

    # Check if any of the dependent packages are already installed.
    for i in "${arg_array[@]}"; do
        printf "  %b Checking for %s..." "${INFO}" "${i}"
        if dpkg-query -W -f='${Status}' "${i}" 2>/dev/null | grep "ok installed" &> /dev/null; then
            printf "%b  %b Checking for %s\\n" "${OVER}" "${TICK}" "${i}"
        else
            echo -e "${OVER}  ${INFO} Checking for $i (will be installed)"
            install_array+=("${i}")
        fi
    done
    # Only install dependent packages that are missing from the system to avoid
    # unecessary downloading
    if [[ "${#install_array[@]}" -gt 0 ]]; then
        if ! (sudo debconf-apt-progress --logfile error_log -- "${PKG_NEW_INSTALL[@]}" "${install_array[@]}"); then
            printf "  %b\\nError: Unable to install dependent packages\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
            printf "%s\\n\\n" "$(<error_log)"
            clean_up
            exit 1
        fi
    fi
}

# UPDATE PYTHON PACKAGE MANAGER: PIP
# ------------------------------------------------------------------------------
update_pip() {
    local str="Updating Python package manager"
    printf "\\n  %b %s..." "${INFO}" "${str}"
    if (${PIP_UPDATE} pip setuptools &> error_log); then
        printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
    else
        printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
        printf "  %bError: Unable to update Python package manager: pip\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<error_log)"
        clean_up
        exit 1
    fi
}

# INSTALL PYTHON MODULES FOR THE WeatherFlow PiConsole
# ------------------------------------------------------------------------------
install_python_modules() {

    # Parse function input and print progress to screen.
    printf "\\n  %b Installing WeatherFlow PiConsole Python modules..." "${INFO}"
    declare -a arg_array=("${PYTHON_MODULES[@]}")
    declare -a install_array

    # Update Python package manager: pip
    update_pip

    # Install required Python modules
    for i in "${arg_array[@]}"; do
        module=$(echo $i | cut -d"[" -f 1 | cut -d"=" -f 1)
        local str="Installing Python module"
        printf "  %b %s %s..." "${INFO}" "${str}" "${module}"
        if (${PIP_INSTALL} "$i" &> error_log); then
            printf "%b  %b %s %s\\n" "${OVER}" "${TICK}" "${str}" "${module}"
        else
            printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
            printf "  %bError: Unable to install Python module: $module\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
            printf "%s\\n\\n" "$(<error_log)"
            clean_up
            exit 1
        fi
    done
}

# UPDATE PYTHON MODULES FOR THE WeatherFlow PiConsole
# ------------------------------------------------------------------------------
update_python_modules() {

    # Parse function input and print progress to screen.
    printf "\\n  %b Updating WeatherFlow PiConsole Python modules..." "${INFO}"
    declare -a arg_array=("${PYTHON_MODULES[@]}")

    # Update Python package manager: pip
    update_pip

    # Get list of installed packages and versions
    python3 -m pip freeze > module_list

    # Update required Python modules
    for i in "${arg_array[@]}"; do
        module=$(echo $i | cut -d"[" -f 1 | cut -d"=" -f 1)
        required_version=$(echo $i | cut -d"=" -f 3)
        if grep -iF $module module_list &> /dev/null; then
            current_version=$(grep -iF $module module_list | cut -d"=" -f 3)
            if [[ "$current_version" != "$required_version" ]]; then
                local str="Updating Python module"
                printf "  %b %s %s..." "${INFO}" "${str}" "${module}"
                if (${PIP_INSTALL} "$i" &> error_log); then
                    printf "%b  %b %s %s\\n" "${OVER}" "${TICK}" "${str}" "${module}"
                else
                    printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
                    printf "  %bError: Unable to update Python module: $module\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
                    printf "%s\\n\\n" "$(<error_log)"
                    clean_up
                    exit 1
                fi
            fi
        else
            local str="Installing new Python module"
            printf "  %b %s %s..." "${INFO}" "${str}" "${module}"
            if (${PIP_INSTALL} "$i" &> error_log); then
                printf "%b  %b %s %s\\n" "${OVER}" "${TICK}" "${str}" "${module}"
            else
                printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
                printf "  %bError: Unable to install Python module: $module\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
                printf "%s\\n\\n" "$(<error_log)"
                clean_up
                exit 1
            fi
        fi
    done
}

# INSTALL PACKAGES REQUIRED BY KIVY PYTHON LIBRARY ON ARM MACHINES
# ------------------------------------------------------------------------------
install_kivy_packages() {

    # Define required packages and print progress to screen
    printf "\\n  %b Kivy Python library dependency checks...\\n" "${INFO}"
    if [[ "$PROCESSOR" = "arm"* ]]; then
        declare -a arg_array=("${KIVY_DEPENDENCIES_ARM[@]}")
    else
        declare -a arg_array=("${KIVY_DEPENDENCIES[@]}")
    fi
    declare -a install_array

    # Check if any of the required packages are already installed.
    for i in "${arg_array[@]}"; do
        printf "  %b Checking for %s..." "${INFO}" "${i}"
        if dpkg-query -W -f='${Status}' "${i}" 2>/dev/null | grep "ok installed" &> /dev/null; then
            printf "%b  %b Checking for %s\\n" "${OVER}" "${TICK}" "${i}"
        else
            echo -e "${OVER}  ${INFO} Checking for $i (will be installed)"
            install_array+=("${i}")
        fi
    done

    # Only install required packages that are missing from the system to avoid
    # unecessary downloading
    if [[ "${#install_array[@]}" -gt 0 ]]; then
        if ! (sudo debconf-apt-progress --logfile error_log -- "${PKG_NEW_INSTALL[@]}" "${install_array[@]}"); then
            printf "  %b\\nError: Unable to install dependent packages\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
            printf "%s\\n\\n" "$(<error_log)"
            clean_up
            exit 1
        fi
    fi
}

# INSTALL KIVY PYTHON LIBRARY
# ------------------------------------------------------------------------------
install_kivy() {

    # Check if required Kivy version is installed
    local str="Kivy Python library installation check"
    printf "\\n  %b %s..." "${INFO}" "${str}"
    if python3 -c "import kivy" &> /dev/null; then
        kivy_version=$(python3 -m pip show kivy | grep Version | cut -d" " -f2)
        if [[ "$KIVY_VERSION" == "$kivy_version" ]]; then
            printf "%b  %b %s \\n" "${OVER}" "${TICK}" "${str}"
        else
            printf "%b  %b %s (will be updated)" "${OVER}" "${INFO}" "${str}"
            local update_kivy=true
        fi
    else
        printf "%b  %b %s (will be installed)" "${OVER}" "${INFO}" "${str}"
        local install_kivy=true
    fi

    # Install Kivy Python library
    if [[ "$update_kivy" = true ]] || [[ "$install_kivy" = true ]]; then
        if [[ "$update_kivy" = true ]]; then
            local str="Updating Kivy Python library"
        else
            local str="Installing Kivy Python library"
        fi
        printf "\\n  %b %s..." "${INFO}" "${str}"
        if ($PIP_INSTALL $KIVY_REPO &> error_log); then
            printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
        else
            printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
            printf "  %bError: Unable to install Kivy Python library\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
            printf "%s\\n\\n" "$(<error_log)"
            clean_up
            exit 1
        fi

        # Update Kivy configuration
        update_kivy_config
    fi
}

# UPDATE KIVY CONFIGURATION
# ------------------------------------------------------------------------------
update_kivy_config() {

    # Create Kivy config file for user that called function
    local str="Updating Kivy configuration for touch screen"
    printf "  %b %s..." "${INFO}" "${str}"
    if python3 -c "import kivy" &> error_log; then
        :
    else
        printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
        printf "  %bError: Unable to update Kivy configuration for touch screen\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<error_log)"
        clean_up
        exit 1
    fi

    # Ensure current user is in input and video groups
    sudo usermod -a -G input,video $USER

    # Echo Python commands to file required to modify the Kivy config for the
    # Raspberry Pi touchscreen
    config_file=$(eval echo "~$USER/.kivy/config.ini")
    echo "import configparser" >> python_command
    echo "Config = configparser.ConfigParser()" >> python_command
    echo "Config.read('$config_file')" >> python_command
    echo "Config.remove_section('input')" >> python_command
    echo "Config.add_section('input')" >> python_command
    echo "Config.set('input','mouse','mouse')" >> python_command
    echo "Config.set('input','mtdev_%(name)s','probesysfs,provider=mtdev')" >> python_command
    echo "Config.set('input','hid_%(name)s','probesysfs,provider=hidinput')" >> python_command
    echo "with open('$config_file','w') as configfile:" >> python_command
    echo "    Config.write(configfile)" >> python_command
    echo "configfile.close()" >> python_command

    # Run Python command to modify Kivy config for the Raspberry Pi touchscreen
    if (python3 python_command &> error_log); then
        printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
    else
        printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
        printf "  %bError: Unable to update Kivy configuration for touch screen\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<error_log)"
        clean_up
        exit 1
    fi
}

# GET THE LATEST VERSION OF THE WeatherFlow PiConsole FROM GITHUB
# ------------------------------------------------------------------------------
get_latest_version() {

    # Get info on latest version from Github API
    local tag_info=$(curl -s $WFPICONSOLE_TAGS -H 'Accept: application/vnd.github.v3+json')
    local latest_version=$(echo $tag_info | jq -r '.[0].name')
    local status=0

    # If the WeatherFlow PiConsole is already installed, get the current
    # installed version from wfpiconsole.ini file.
    if [[ -f $CONSOLEDIR/wfpiconsole.ini ]]; then
        current_version=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$CONSOLEDIR/wfpiconsole.ini'); print(c['System']['Version'])")
        printf "\\n  %b Latest version of WeatherFlow PiConsole: %s" ${INFO} ${latest_version}
        printf "\\n  %b Installed version of WeatherFlow PiConsole: %s" ${INFO} ${current_version}

        # Compare current version with latest version. If versions match, there
        # is no need to get the latest version, but make sure we are on the main
        # branch
        if [[ "$current_version" == "$latest_version" ]]; then
            printf "\\n  %b Versions match: %bNo update required%b\n" "${TICK}" "${COL_LIGHT_GREEN}" "${COL_NC}"
            if (is_repo ${CONSOLEDIR}); then
                local current_branch=$(git -C ${CONSOLEDIR} rev-parse --abbrev-ref HEAD)
                if [[ "${current_branch}" != "main" ]]; then
                    git -C ${CONSOLEDIR} checkout main &> error_log || return $?
                fi
                git -C ${CONSOLEDIR} reset --hard "$(git -C ${CONSOLEDIR} describe --abbrev=0 --tags)" &> error_log || return $?
            fi
            return

        # Else, get the latest version of the WeatherFlow PiConsole
        else
            local str="Updating WeatherFlow PiConsole to ${COL_LIGHT_GREEN}${latest_version}${COL_NC}"
            printf "\\n\\n  %b %b..." "${INFO}" "${str}"
            if (is_repo ${CONSOLEDIR}); then
                if (update_repo_latest_tag ${CONSOLEDIR} &> error_log); then status=1; fi
            else
                if (create_repo ${CONSOLEDIR} ${WFPICONSOLE_REPO} &> error_log); then status=1; fi
            fi
            if [[ $status -eq 1 ]]; then
                printf "%b  %b %b\\n" "${OVER}" "${TICK}" "${str}"
            else
              printf "%b  %b %b\\n" "${OVER}" "${CROSS}" "${str}"
              printf "  %bError: Unable to update WeatherFlow PiConsole\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
              printf "%s\\n\\n" "$(<error_log)"
              clean_up
              exit 1
          fi
        fi

    # Else, the WeatherFlow PiConsole is not installed so get the latest stable
    # version
    else
        local str="Installing latest version of WeatherFlow PiConsole: ${COL_LIGHT_GREEN}${latest_version}${COL_NC}"
        printf "\\n  %b %b..." "${INFO}" "${str}"
        if (is_repo ${CONSOLEDIR} &> error_log); then
            if (update_repo_latest_tag ${CONSOLEDIR} &> error_log); then status=1; fi
        else
            if (create_repo ${CONSOLEDIR} ${WFPICONSOLE_REPO} &> error_log); then status=1; fi
        fi
        if [[ $status -eq 1 ]]; then
            printf "%b  %b %b\\n" "${OVER}" "${TICK}" "${str}"
        else
          printf "%b  %b %b\\n" "${OVER}" "${CROSS}" "${str}"
          printf "  %bError: Unable to install WeatherFlow PiConsole\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
          printf "%s\\n\\n" "$(<error_log)"
          clean_up
          exit 1
      fi
    fi

    # Ensure console directory is owned by the correct user
    console_owner=$(stat -c "%U" $CONSOLEDIR)
    if [[ "$console_owner" != "$USER" ]]; then
        sudo chown -fR $USER $CONSOLEDIR
        sudo chgrp -fR $USER $CONSOLEDIR
    fi

    # Make sure wfpiconsole.sh file is executable and create symlink to
    # usr/bin/local so function can be called directly from the command line
    chmod 744 $CONSOLEDIR/wfpiconsole.sh
    sudo ln -sf $CONSOLEDIR/wfpiconsole.sh /usr/local/bin/wfpiconsole
}

# SWITCH TO THE WeatherFlow PiConsole STABLE BRANCH
# ------------------------------------------------------------------------------
switch_stable_branch() {

    # Switch to the WeatherFlow PiConsole stable branch
    local status=0
    local str="Switching to stable branch"
    printf "  %b %b..." "${INFO}" "${str}"
    if (is_repo ${CONSOLEDIR}); then
        if (switch_repo_stable ${CONSOLEDIR}); then status=1; fi
    fi
    if [[ $status -eq 1 ]]; then
        printf "%b  %b %b\\n" "${OVER}" "${TICK}" "${str}"
    else
        printf "%b  %b %b\\n" "${OVER}" "${CROSS}" "${str}"
        printf "  %bError: Unable to switch to WeatherFlow PiConsole stable branch\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<error_log)"
        clean_up
        exit 1
    fi

    # Ensure console directory is owned by the correct user
    console_owner=$(stat -c "%U" $CONSOLEDIR)
    if [[ "$console_owner" != "$USER" ]]; then
        sudo chown -fR $USER $CONSOLEDIR
        sudo chgrp -fR $USER $CONSOLEDIR
    fi
}

# SWITCH TO THE WeatherFlow PiConsole BETA BRANCH
# ------------------------------------------------------------------------------
switch_beta_branch() {

    # Switch to the WeatherFlow PiConsole beta branch
    local status=0
    local str="Switching to WeatherFlow PiConsole beta branch"
    printf "  %b %b..." "${INFO}" "${str}"
    if (is_repo ${CONSOLEDIR}); then
        if (switch_repo_beta ${CONSOLEDIR}); then status=1; fi
    fi
    if [[ $status -eq 1 ]]; then
        printf "%b  %b %b\\n" "${OVER}" "${TICK}" "${str}"
    else
        printf "%b  %b %b\\n" "${OVER}" "${CROSS}" "${str}"
        printf "  %bError: Unable to switch to WeatherFlow PiConsole beta branch\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<error_log)"
        clean_up
        exit 1
    fi

    # Ensure console directory is owned by the correct user
    console_owner=$(stat -c "%U" $CONSOLEDIR)
    if [[ "$console_owner" != "$USER" ]]; then
        sudo chown -fR $USER $CONSOLEDIR
        sudo chgrp -fR $USER $CONSOLEDIR
    fi
}

# INSTALL THE wfpiconsole.service FILE TO /etc/systemd/system/
# ------------------------------------------------------------------------------
install_service_file () {

    # Write current user and install directory to wfpiconsole.service file
    sed -i "s+WorkingDirectory=.*$+WorkingDirectory=$CONSOLEDIR+" $CONSOLEDIR/wfpiconsole.service
    sed -i "s+User=.*$+User=$USER+" $CONSOLEDIR/wfpiconsole.service
    sed -i "s+StandardOutput=.*$+StandardOutput=file:${CONSOLEDIR}wfpiconsole.log+" $CONSOLEDIR/wfpiconsole.service
    sed -i "s+StandardError=.*$+StandardError=file:${CONSOLEDIR}wfpiconsole.log+" $CONSOLEDIR/wfpiconsole.service

    # Install wfpiconsole.service file to /etc/systemd/system/ and reload deamon
    local str="Copying service file to autostart directory"
    printf "  %b %s..." "${INFO}" "${str}"
    sudo cp $CONSOLEDIR/wfpiconsole.service /etc/systemd/system/
    if (sudo systemctl daemon-reload &> error_log); then
        printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
    else
        printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
        printf "  %bError: Unable to install wfpiconsole.service file\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<error_log)"
        clean_up
        exit 1
    fi
}

# ENABLE THE wfpiconsole.service
# ------------------------------------------------------------------------------
enable_service () {

    # Enable wfpiconsole.service file
    local str="Enabling WeatherFlow PiConsole service file"
    printf "  %b %s..." "${INFO}" "${str}"
    rm -f wfpiconsole.log
    if (sudo systemctl enable wfpiconsole &> error_log); then
        if (sudo systemctl start wfpiconsole &> error_log); then
            printf "%b  %b %s\\n\\n" "${OVER}" "${TICK}" "${str}"
        else
            printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
            printf "  %bError: Unable to enable WeatherFlow PiConsole service file\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
            printf "%s\\n\\n" "$(<error_log)"
            clean_up
            exit 1
        fi
    else
        printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
        printf "  %bError: Unable to enable WeatherFlow PiConsole service file\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<error_log)"
        clean_up
        exit 1
    fi
}

# DISABLE THE wfpiconsole.service
# ------------------------------------------------------------------------------
disable_service () {

    # Disable the wfpiconsole service
    local str="Disabling WeatherFlow PiConsole service file"
    printf "  %b %s..." "${INFO}" "${str}"
    if (sudo systemctl disable wfpiconsole.service &> error_log); then
        printf "%b  %b %s\\n\\n" "${OVER}" "${TICK}" "${str}"
    else
        printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
        printf "  %bError: Unable to disable WeatherFlow PiConsole service file\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
        printf "%s\\n\\n" "$(<error_log)"
        clean_up
        exit 1
    fi
}

# CHECK IF DIRECTORY IS A GIT REPOSITORY
# ------------------------------------------------------------------------------
is_repo() {

    local directory=${1}
    if [[ -d ${directory} ]]; then
        git -C ${directory} status --short &> error_log || local rc=$?
    else
        local rc=1
    fi
    return "${rc:-0}"
}

# CREATE NEW GIT REPOSITORY AT LATEST MAIN BRANCH RELEASE
# ------------------------------------------------------------------------------
create_repo() {

    # If the directory already exists, turn it into a git directory, otherwise
    # clone the git repository directly
    local directory=${1}
    local repository=${2}
    if [[ -d ${directory} ]]; then
        git clone --no-checkout ${repository} ${directory}/temp &> error_log || return $?
        mv ${directory}/temp/.git ${directory}/.git
        rmdir ${directory}/temp
        git -C ${directory} reset --hard HEAD &> error_log || return $?
    else
        git clone ${repository} ${directory} &> error_log || return $?
    fi

    # Checkout the main branch if required and reset code to latest tag
    local current_branch=$(git rev-parse --abbrev-ref HEAD)
    if [[ "${current_branch}" != "main" ]]; then
        git -C ${directory} checkout main &> error_log || return $?
    fi
    git -C ${directory} reset --hard "$(git -C ${directory} describe --abbrev=0 --tags)" &> error_log || return $?
}

# UPDATE GIT REPOSITORY TO LATEST MAIN BRANCH RELEASE
# ------------------------------------------------------------------------------
update_repo_latest_tag() {

    # Clear all changes from local git repository and remove Python bytecode to
    # ensure directory contents always matches the Git repository
    local directory=${1}
    find ${directory} -type d -name __pycache__ -exec rm -r {} +
    git -C ${directory} checkout . &> error_log || return $?
    git -C ${directory} clean --force -d &> error_log || true

    # Checkout the main branch if required and pull latest commits. Reset code
    # to most recent release
    local current_branch=$(git -C ${directory} rev-parse --abbrev-ref HEAD)
    if [[ "${current_branch}" != "main" ]]; then
        git -C ${directory} checkout main &> error_log || return $?
    fi
    git -C ${directory} pull &> error_log || return $?
}

# SWITCH GIT REPOSITORY TO LATEST MAIN BRANCH COMMIT
# ------------------------------------------------------------------------------
switch_repo_stable() {

    # Clear all changes from local git repository and remove Python bytecode to
    # ensure directory contents always matches the Git repository
    local directory=${1}
    find ${directory} -type d -name __pycache__ -exec rm -r {} +
    git -C ${directory} checkout . &> error_log || return $?
    git -C ${directory} clean --force -d &> error_log || true

    # Checkout the main branch if required and pull latest commits
    local current_branch=$(git -C ${directory} rev-parse --abbrev-ref HEAD)
    if [[ "${current_branch}" != "main" ]]; then
        git -C ${directory} checkout main &> error_log || return $?
    fi
    git -C ${directory} pull &> error_log || return $?
}

# SWITCH GIT REPOSITORY TO LATEST DEVELOP BRANCH COMMIT
# ------------------------------------------------------------------------------
switch_repo_beta() {

    # Clear all changes from local git repository and remove Python bytecode to
    # ensure directory contents always matches the Git repository
    local directory=${1}
    find ${directory} -type d -name __pycache__ -exec rm -r {} +
    git -C ${directory} checkout . &> error_log || return $?
    git -C ${directory} clean --force -d &> error_log || true

    # Checkout the develop branch if required and pull latest commits
    local current_branch=$(git -C ${directory} rev-parse --abbrev-ref HEAD)
    if [[ "${current_branch}" != "develop" ]]; then
        git -C ${directory} checkout develop &> error_log || return $?
    fi
    git -C ${directory} pull &> error_log || return $?
}

# DISPLAY REQUIRED PROCESS STARTING DIALOGUE
# ------------------------------------------------------------------------------
process_starting() {

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
        run_update)
            printf "\\n"
            printf "  ============================== \\n"
            printf "  Updating WeatherFlow PiConsole \\n"
            printf "  ============================== \\n\\n"
            ;;
    # Display stable starting dialogue
        stable)
            printf "\\n"
            printf "  ============================== \\n"
            printf "  Switching to the stable branch \\n"
            printf "  ============================== \\n\\n"
            ;;
    # Display update starting dialogue
        run_beta)
            printf "\\n"
            printf "  ============================ \\n"
            printf "  Switching to the beta branch \\n"
            printf "  ============================ \\n\\n"
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
process_complete() {

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
        run_update)
            printf "  \\n"
            printf "  ============================================= \\n"
            printf "  WeatherFlow PiConsole update complete!        \\n"
            printf "  Restart the console with: 'wfpiconsole start' \\n"
            printf "  or 'wfpiconsole autostart-enable'             \\n"
            printf "  ============================================= \\n\\n"
            ;;
    # Display patch complete dialogue
        stable)
            printf "  \\n"
            printf "  ============================================= \\n"
            printf "  Switch to stable branch complete!             \\n"
            printf "  Restart the console with: 'wfpiconsole start' \\n"
            printf "  or 'wfpiconsole autostart-enable'             \\n"
            printf "  ============================================= \\n\\n"
            ;;
    # Display beta complete dialogue
        run_beta)
            printf "  \\n"
            printf "  ============================================= \\n"
            printf "  Switch to beta branch complete!               \\n"
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
    if (sudo systemctl | grep wfpiconsole.service &> error_log); then
        sudo systemctl stop wfpiconsole.service
    else
        pkill -HUP -f main.py
    fi
    clean_up
}

# INSTALL THE WeatherFlow PiConsole
# ------------------------------------------------------------------------------
install() {

    # Display installation starting dialogue
    process_starting ${FUNCNAME[0]}
    # Check for and ask user if they wish to install any updated local packages
    update_packages
    # Install required packages
    install_packages
    # Install required Python modules
    install_python_modules
    # Install required Kivy dependencies
    install_kivy_packages
    # Install Kivy Python library
    install_kivy
    # Get the latest version of the WeatherFlow PiConsole and install
    get_latest_version
    # Clean up after update
    clean_up
    # Display installation complete dialogue
    process_complete ${FUNCNAME[0]}
}

# UPDATE THE WeatherFlow PiConsole TO THE LATEST STABLE VERSION
# ------------------------------------------------------------------------------
update() {

    # Fetch the latest update code directly from the main Github branch. This
    # ensures that changes in dependencies are addressed during this update
    curl -sSL $WFPICONSOLE_MAIN_UPDATE | bash -s run_update
}

run_update() {

    # Display installation starting dialogue
    process_starting ${FUNCNAME[0]}
    # Check for and ask user if they wish to install any updated local packages
    update_packages
    # Check if any new dependencies are required
    install_packages
    # Update Python modules as required
    update_python_modules
    # Install required Kivy dependencies
    install_kivy_packages
    # Install Kivy Python library
    install_kivy
    # Get the latest version of the WeatherFlow PiConsole and install
    get_latest_version
    # Clean up after installation
    clean_up
    # Display update complete dialogue
    process_complete ${FUNCNAME[0]}
}

# SWITCH THE WeatherFlow PiConsole TO THE STABLE BRANCH
# ------------------------------------------------------------------------------
stable() {

    # Display installation starting dialogue
    process_starting ${FUNCNAME[0]}
    # Get the latest patch for the WeatherFlow PiConsole and install
    switch_stable_branch
    # Clean up after installation
    clean_up
    # Display update complete dialogue
    process_complete ${FUNCNAME[0]}
}

# SWITCH THE WeatherFlow PiConsole TO THE BETA BRANCH
# ------------------------------------------------------------------------------
beta() {

    # Fetch the latest beta update code directly from the develop Github branch.
    # This ensures that changes in dependencies are addressed during this update
    curl -sSL $WFPICONSOLE_BETA_UPDATE | bash -s run_beta
}

run_beta() {

    # Display installation starting dialogue
    process_starting ${FUNCNAME[0]}
    # Check for and ask user if they wish to install any updated local packages
    update_packages
    # Check if any new dependencies are required
    install_packages
    # Update Python modules as required
    update_python_modules
    # Install required Kivy dependencies
    install_kivy_packages
    # Install Kivy Python library
    install_kivy
    # Switch to the WeatherFlow PiConsole beta branch
    switch_beta_branch
    # Clean up after installation
    clean_up
    # Display update complete dialogue
    process_complete ${FUNCNAME[0]}
}

# SET THE WeatherFlow PiConsole TO START AUTOMATICALLY
# ------------------------------------------------------------------------------
autostart-enable () {

    # Display autostart-enable starting dialogue
    process_starting ${FUNCNAME[0]}
    # Edit and install wfpiconsole.service file
    install_service_file
    # Enable wfpiconsole service
    enable_service
    # Clean up after enabling autostart
    clean_up
    # Display autostart-enable complete dialogue
    process_complete ${FUNCNAME[0]}
}

# DISABLE THE WeatherFlow PiConsole FROM STARTING AUTOMATICALLY
# ------------------------------------------------------------------------------
autostart-disable () {

    # Display autostart-disable starting dialogue
    process_starting ${FUNCNAME[0]}
    # Disable wfpiconsole service
    disable_service
    # Clean up after disabling autostart
    clean_up
    # Display autostart-disable complete dialogue
    process_complete ${FUNCNAME[0]}
}

# SCRIPT USAGE
# ------------------------------------------------------------------------------
help_func() {
  echo "Usage: wfpiconsole [options]
Example: 'wfpiconsole update'

Options:
  start                 : Start the WeatherFlow PiConsole
  stop                  : Stop the WeatherFlow PiConsole
  install               : Install the WeatherFlow PiConsole
  update                : Update the WeatherFlow PiConsole
  stable                : Switch the WeatherFlow PiConsole to the stable branch
  beta                  : Switch the WeatherFlow PiConsole to the beta branch
  autostart-enable      : Set the WeatherFlow PiConsole to autostart at boot
  autostart-disable     : Stop the WeatherFlow PiConsole autostarting at boot"
  exit 0
}

# SCRIPT CALLED WITH NO ARGUMENTS. PRINT HELP FUNCTION
# ------------------------------------------------------------------------------
if [ $# -eq 0 ]; then
    printf "Unrecognised usage\\n"
    help_func
fi

# ENSURE ROOT ACCESS IS AVAILABLE
# ------------------------------------------------------------------------------
# Ensure sudo command is available and script can be elevated to root privileges
if [[ ! -x "$(command -v sudo)" ]]; then
    printf "\\n"
    printf "  %bError: Unable to $1 the WeatherFlow PiConsole.\\n\\n%b" "${COL_LIGHT_RED}" "${COL_NC}"
    printf "  sudo is needed to $1 the WeatherFlow PiConsole\\n"
    printf "  Please install sudo and run this script again Pi\\n\\n"
    clean_up
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
        clean_up
        exit 1
    fi
fi

# CHECK OS/HARDWARE AND ADD REQUIRED REPOSITORIES WHEN INSTALL OR UPDATING
# ------------------------------------------------------------------------------
if [[ "${1}" == "install" ]] || [[ "${1}" == "run_update" ]] || [[ "${1}" == "run_beta" ]] || [[ "${1}" == "stable" ]] ; then

    # Check compatability of hardware/OS
    PROCESSOR=$(uname -m)
    if [[ $PROCESSOR = arm* ]] || [[ $PROCESSOR = x86_64 ]] || [[ $PROCESSOR = i*86 ]] || [[ $PROCESSOR = aarch64 ]]; then
        printf "  %b Hardware check passed (%b)\\n" "${TICK}" "${PROCESSOR}"
    else
        printf "  %b Hardware check failed (%b)\\n\\n" "${CROSS}" "${PROCESSOR}"
        clean_up
        exit 1
    fi
    OS=$(. /etc/os-release && echo $PRETTY_NAME)
    if is_command apt-get ; then
        printf "  %b OS check passed (%b)\\n" "${TICK}" "${OS}"
    else
        printf "  %b OS check failed (%b)\\n\\n" "${CROSS}" "${OS}"
        clean_up
        exit 1
    fi

    # Add "universe" repository when running Ubtuntu if required
    if echo $OS | grep -iF "Ubuntu" &> /dev/null; then
        if ! (find /etc/apt/ -name *.list | xargs cat | grep universe &> /dev/null); then
            str="Enabling Universe repository in Ubuntu"
            printf "  %b %s..." "${INFO}" "${str}"
            if (sudo add-apt-repository universe &> error_log); then
                printf "%b  %b %s\\n" "${OVER}" "${TICK}" "${str}"
            else
                printf "%b  %b %s\\n" "${OVER}" "${CROSS}" "${str}"
                printf "  %bError: Unable to enabling Universe repository.\\n\\n %b" "${COL_LIGHT_RED}" "${COL_NC}"
                printf "%s\\n\\n" "$(<error_log)"
                clean_up
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
    "stable"              ) stable;;
    "beta"                ) beta;;
    "run_update"          ) run_update;;
    "runUpdate"           ) run_update;;
    "run_beta"            ) run_beta;;
    "runBeta"             ) run_beta;;
    "autostart-enable"    ) autostart-enable;;
    "autostart-disable"   ) autostart-disable;;
    *                     ) printf "Unrecognised usage\\n" && help_func;;
esac
