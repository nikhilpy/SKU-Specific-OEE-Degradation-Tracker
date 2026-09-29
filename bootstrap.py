import os
import sys
import subprocess
import venv
import shutil
import platform

# ANSI escape codes for colors
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_color(message, color=Colors.OKGREEN):
    print(f"{color}{message}{Colors.ENDC}")

def get_venv_python():
    system = platform.system().lower()
    if system == 'windows':
        return os.path.join('.venv', 'Scripts', 'python.exe')
    else:
        return os.path.join('.venv', 'bin', 'python')

def get_venv_pip():
    system = platform.system().lower()
    if system == 'windows':
        return os.path.join('.venv', 'Scripts', 'pip.exe')
    else:
        return os.path.join('.venv', 'bin', 'pip')

def get_venv_streamlit():
    system = platform.system().lower()
    if system == 'windows':
        return os.path.join('.venv', 'Scripts', 'streamlit.exe')
    else:
        return os.path.join('.venv', 'bin', 'streamlit')

def run_command(command, error_message, cwd=None):
    try:
        subprocess.run(command, check=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        print_color(f"{error_message}: {e}", Colors.FAIL)
        return False
    except Exception as e:
        print_color(f"{error_message}: {e}", Colors.FAIL)
        return False
    return True

def setup():
    print_color("Starting Bootstrap Process...", Colors.HEADER)
    
    # 1. Detect OS
    system = platform.system()
    print_color(f"Detected OS: {system}", Colors.OKCYAN)

    # 2. Idempotently create a .venv if it doesn't exist
    if not os.path.exists('.venv'):
        print_color("Creating virtual environment '.venv'...", Colors.OKCYAN)
        venv.create('.venv', with_pip=True)
    else:
        print_color("Virtual environment '.venv' already exists.", Colors.OKCYAN)
        
    python_exe = get_venv_python()
    pip_exe = get_venv_pip()

    if not os.path.exists(python_exe) or not os.path.exists(pip_exe):
         print_color(f"Virtual environment seems corrupted. Cannot find {python_exe} or {pip_exe}.", Colors.FAIL)
         return

    # 3. Upgrade pip and install requirements.txt
    print_color("Upgrading pip...", Colors.OKCYAN)
    run_command([python_exe, '-m', 'pip', 'install', '--upgrade', 'pip'], "Failed to upgrade pip")
    
    if os.path.exists('requirements.txt'):
        print_color("Installing requirements.txt...", Colors.OKCYAN)
        run_command([pip_exe, 'install', '-r', 'requirements.txt'], "Failed to install requirements")
    else:
        print_color("requirements.txt not found. Skipping python dependencies.", Colors.WARNING)

    # 4. Check for npm via shutil.which
    print_color("Checking for npm...", Colors.OKCYAN)
    npm_path = shutil.which('npm')
    if npm_path:
        # npm install command has an issue where it creates node_modules on execution directory.
        # Ensure we run this at the root. (Which we are)
        if os.path.exists('package.json'):
            if not os.path.exists('node_modules'):
                print_color("node_modules not found. Running npm install...", Colors.OKCYAN)
                run_command([npm_path, 'install'], "Failed to run npm install")
            else:
                print_color("node_modules already exists. Skipping npm install.", Colors.OKCYAN)
        else:
            print_color("package.json not found. Skipping npm install.", Colors.WARNING)
    else:
        print_color("Warning: npm not found on PATH. Please install Node.js and npm.", Colors.WARNING)

    # 5. Check for ollama via shutil.which
    print_color("Checking for ollama...", Colors.OKCYAN)
    ollama_path = shutil.which('ollama')
    if ollama_path:
        print_color("Running ollama list...", Colors.OKCYAN)
        try:
            result = subprocess.run([ollama_path, 'list'], capture_output=True, text=True, check=True)
            if 'llama3.2:latest' not in result.stdout.lower():
                print_color("'llama3.2:latest' model not found. Pulling llama3.2:latest...", Colors.OKCYAN)
                run_command([ollama_path, 'pull', 'llama3.2:latest'], "Failed to pull llama3.2:latest model")
            else:
                print_color("'llama3.2:latest' model already pulled.", Colors.OKCYAN)
        except subprocess.CalledProcessError as e:
            print_color(f"Failed to run ollama list: {e}", Colors.WARNING)
        except Exception as e:
            print_color(f"Warning: Unexpected error with ollama: {e}", Colors.WARNING)

        # 5b. Ensure ollama serve is running (check port 11434)
        print_color("Checking if ollama server is running...", Colors.OKCYAN)
        import urllib.request, urllib.error
        ollama_running = False
        try:
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
            ollama_running = True
            print_color("Ollama server is already running.", Colors.OKCYAN)
        except Exception:
            ollama_running = False

        if not ollama_running:
            print_color("Starting ollama serve in the background...", Colors.OKCYAN)
            try:
                subprocess.Popen(
                    [ollama_path, 'serve'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if platform.system().lower() == 'windows' else 0
                )
                import time
                # Give the server a moment to be ready before Streamlit imports llm.py
                for i in range(6):
                    time.sleep(1)
                    try:
                        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
                        print_color("Ollama server is ready.", Colors.OKGREEN)
                        break
                    except Exception:
                        pass
                else:
                    print_color("Warning: Ollama server may not be ready yet. The LLM agent will retry.", Colors.WARNING)
            except Exception as e:
                print_color(f"Warning: Could not start ollama serve automatically: {e}", Colors.WARNING)
    else:
         print_color("Warning: ollama not found on PATH. Please install Ollama.", Colors.WARNING)

    print_color("\nSetup complete!", Colors.OKGREEN)
    
    # 6. Prompt to run tests
    while True:
        try:
            run_tests = input("Do you want to run the test suite to verify the setup? (y/n): ").strip().lower()
            if run_tests == 'y':
                print_color("Running tests...", Colors.OKCYAN)
                # Using python -m pytest to ensure it runs in the virtualenv context correctly
                run_command([python_exe, '-m', 'pytest', 'tests/', '-v'], "Tests failed.")
                break
            elif run_tests == 'n':
                print_color("Skipping tests.", Colors.OKCYAN)
                break
            else:
                print("Please enter 'y' or 'n'.")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            return

    # 7. Prompt the user to start the app
    while True:
        try:
            response = input("Do you want to start the Streamlit Command Center now? (y/n): ").strip().lower()
            if response == 'y':
                print_color("Starting Streamlit Command Center...", Colors.OKCYAN)
                streamlit_exe = get_venv_streamlit()
                if os.path.exists(streamlit_exe):
                     try:
                         # Launch streamlit
                         subprocess.run([streamlit_exe, "run", "code/streamlit_app/app.py"])
                     except Exception as e:
                         print_color(f"Failed to start Streamlit: {e}", Colors.FAIL)
                else:
                     print_color(f"Streamlit executable not found at {streamlit_exe}. Did it install correctly?", Colors.FAIL)
                break
            elif response == 'n':
                print_color("Exiting. You can start the app later.", Colors.OKGREEN)
                break
            else:
                print("Please enter 'y' or 'n'.")
        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except EOFError:
             print("\nExiting.")
             break


if __name__ == '__main__':
    # Initialize ANSI colors for windows terminal
    if platform.system().lower() == 'windows':
        os.system('color')
    setup()
