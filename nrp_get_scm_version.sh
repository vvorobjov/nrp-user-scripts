#!/bin/bash


# The function for calculating the version from the git repository.
# The version is calculated as follows:

# X.Y.Z[+D][.revHASH], where

# X.Y - the digits are taken from the last tag, this is the main version
# Z - is the number of the commits in master branch after the last tag + the third digit in the tag itself. So, if the last tag is 3.3.4, and there are 2 commits in the master branch, the result is 3.3.6. So, the Z is reserved for the patches.
# D - is the number of commits in development branch after its deviation from the master.
# HASH - is the short commit hash in the feature branch (not development and not master). In this case, the D value is incremented (+1) as well. This is done because of the versioning order convention in PyPi.

# So, the master branch has the versions in the form X.Y.Z, development - X.Y.Z+D, the other branches X.Y.Z+D.revHASH

# For example, the sorted versions list might look like
# 3.3.0
# 3.3.1
# 3.3.1+1
# 3.3.1+2
# 3.3.1+3.rev1a2b3d ← this is why +1 is added, because such versions are considered to be younger
# 3.3.1+3
# 3.3.2

function get_scm_version {
  # get latest tag X.Y.Z
  tag=$(git describe --tags --abbrev=0)
  # get version as X.Y
  version="$(cut -d '.' -f 1,2 <<< "$tag")"
  # get patch as Z
  base_patch="$(cut -d '.' -f 3 <<< "$tag")"
  base_patch=${base_patch:-"0"}
  # get distance from master branch to the tag as PATCH
  patch=$(git rev-list --left-right --count origin/master..."$tag" | cut -f 1)
  # sum up initial patch number and the number of commits in master
  patch=$((patch + base_patch))

  # get branch name
  branch_name=$(git branch --show-current)

  # 
  suffix=""
  if [ "$branch_name" = "master" ]; then
    # do nothing for the master branch, the resulting version is X.Y.patch
    suffix=""
  elif [ "$branch_name" = "development" ]; then
    # get distance from development branch to the master
    distance=$(git rev-list --left-right --count HEAD...origin/master | cut -f 1)
    # if development is ahead, add new subversion as +distance
    if [ "$distance" -ne "0" ]; then
      suffix="+$distance"
    fi
  else
    # get distance from development branch to the master
    distance=$(git rev-list --left-right --count origin/development...origin/master | cut -f 1)
    # get distance from current branch to the development
    dev_distance=$(git rev-list --left-right --count HEAD...origin/development | cut -f 1)
    hash=$(git rev-parse --short HEAD)
    # if the distance from current branch to the development is not zero
    # create a pre-version for the next development version
    # +(distance + 1).devHASH
    if [ "$dev_distance" -ne "0" ]; then
      suffix="+"$((distance + 1))".rev$hash"
    fi
  fi
  
  # The resulting version is X.Y.patch[+development-distance][(+1).revHASH-non-development-branch]
  echo -n "${version}.${patch}${suffix}"
}

## The function for writing the calculated version to version files of the repositories
function set_scm_version {
  # shellcheck source=/dev/null
  source "${HBP}/nrp-user-scripts/repos.txt"
  export NRP_INSTALL_MODE=user

  # update Python modules versions
  for i in "${nrp_python[@]}"; do
    cp -f "$HBP/nrp-user-scripts/config_files/user_makefile" "$HBP/$i"
    pushd "$HBP/$i" || continue
      make set-nrp-version
    popd
  done

  # update js versions
  for i in "${nrp_js[@]}"; do
    pushd "$HBP/$i" || continue
      versionSCM=$(get_scm_version)
      sed -i "s|\"version\".*\".*\"|\"version\": \"$versionSCM\"|" package.json
    popd
  done
}

"$@"
