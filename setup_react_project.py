import os
import subprocess
import sys

def setup_react_project():
    project_path = r"D:\All Projects\My AI Agent\react-project"
    
    # Check if project already exists
    if os.path.exists(project_path):
        print("React project already exists. Setting up folder structure...")
    else:
        print("Creating React project...")
        try:
            # Create React app
            subprocess.check_call(['npx', 'create-react-app', 'react-project'], cwd=r"D:\All Projects\My AI Agent")
            print("Successfully created React project")
        except subprocess.CalledProcessError as e:
            print(f"Failed to create React project: {e}")
            return
        except FileNotFoundError:
            print("npx is not installed or not found in PATH. Please install Node.js and npm.")
            return
    
    # Navigate to project directory
    os.chdir(project_path)
    
    # Install Material-UI (chosen UI library)
    try:
        subprocess.check_call(['npm', 'install', '@mui/material', '@mui/icons-material', '@emotion/react', '@emotion/styled'])
        print("Successfully installed Material-UI and dependencies")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install Material-UI: {e}")
        return
    except FileNotFoundError:
        print("npm is not installed or not found in PATH")
        return
    
    # Create folder structure
    folders = [
        'src/components',
        'src/pages',
        'src/hooks',
        'src/context',
        'src/utils',
        'src/assets',
        'src/styles'
    ]
    
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        print(f"Created folder: {folder}")
    
    print("React project environment setup completed successfully!")

if __name__ == "__main__":
    setup_react_project()