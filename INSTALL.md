Installation Instructions for rbot
==================================

Below are the step-by-step instructions for all the prerequisites needed to install rbot. Please follow the section that corresponds to your operating system: Mac, Windows, or Linux.

### Prerequisites

-   Python 3.8 or above
-   pip (Python package installer)
-   (Optional) Microsoft Visual Studio Code or any other Integrated Development Environment (IDE) of your choice.

#### MacOS

1.  Install Homebrew. It is a package manager for MacOS. You can install it by pasting the following command at a Terminal prompt:

    ```bash
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    ```
2.  Install Python 3 and pip using Homebrew:

    ```bash
    brew install python
    ```


3.  (Optional) If you do not have an IDE installed or prefer to use Visual Studio Code, you can install it using the following command:

    ```bash
    brew install --cask visual-studio-code
    ```

#### Windows

1.  Install Python and pip: Download the latest version of Python from the official website here: <https://www.python.org/downloads/windows/>
2.  (Optional) Install Visual Studio Code: Download the installer from the official site: <https://code.visualstudio.com/download>
3.  During the Python installation, make sure to check the box that says "Add Python to PATH" before you click on "Install Now".

#### Linux

1.  You can install Python and pip using the package manager that comes with your distribution. For Ubuntu, you can use the following commands:

    ```bash
    sudo apt-get update
    sudo apt-get install python3
    sudo apt-get install python3-pip
    ```

2.  (Optional) To install Visual Studio Code on Ubuntu, you can use the following commands:

    ```bash
    sudo apt update
    sudo apt install software-properties-common apt-transport-https wget
    wget -q https://packages.microsoft.com/keys/microsoft.asc -O- | sudo apt-key add -
    sudo add-apt-repository "deb [arch=amd64] https://packages.microsoft.com/repos/vscode stable main"
    sudo apt update
    sudo apt install code
    ```

For other Linux distributions, please follow the respective package manager commands to install Python, pip and Visual Studio Code.

### Running rbot

Once you have Python and pip installed, you can download the rbot code from its GitHub repository and install its dependencies using pip.

1.  Clone the rbot repository from GitHub:

    ```bash
    git clone https://github.com/rajivpant/rbot.git
    ```

2.  Navigate to the rbot directory:

    ```bash
    cd rbot
    ```

3.  Install the Python package dependencies including APIs to access LLM engines:

    ```bash
    pip install -r requirements.txt
    ```

4.  You're all set to configure, personalize, and run rbot!
    Read the [configuration and personaliation guide](CONFIGURE.MD) and the [main documentation](README.md).

* * * * *

Remember, while Visual Studio Code is a popular and powerful IDE, its installation is entirely optional. You may use any other text editor or IDE you're comfortable with to explore and contribute to the rbot project. Happy coding!

