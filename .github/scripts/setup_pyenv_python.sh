#!/usr/bin/env bash

set -euo pipefail

PYTHON_VERSION="${1:?python version is required}"

export DEBIAN_FRONTEND=noninteractive

sudo apt-get update
sudo apt-get install -y \
  build-essential \
  clang \
  curl \
  libbz2-dev \
  libffi-dev \
  liblzma-dev \
  libncurses5-dev \
  libncursesw5-dev \
  libreadline-dev \
  libsqlite3-dev \
  libssl-dev \
  llvm \
  make \
  tk-dev \
  xz-utils \
  zlib1g-dev

curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash

export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
eval "$(pyenv init --path)"

CC=clang pyenv install -s "${PYTHON_VERSION}" -v
pyenv global "${PYTHON_VERSION}"

if [[ -n "${GITHUB_PATH:-}" ]]; then
  echo "${PYENV_ROOT}/bin" >> "${GITHUB_PATH}"
  echo "${PYENV_ROOT}/shims" >> "${GITHUB_PATH}"
fi

if [[ -n "${GITHUB_ENV:-}" ]]; then
  echo "PYENV_ROOT=${PYENV_ROOT}" >> "${GITHUB_ENV}"
  echo "PYENV_VERSION=${PYTHON_VERSION}" >> "${GITHUB_ENV}"
fi

python -VV
python -m site
