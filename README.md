# GCT555 Project Base

This project consists of a Python-based server for motion tracking (Face, Hand, Pose) using MediaPipe, and a Unity-based client for visualization and interaction.

## Project Structure

This repository is organized into two main components:

- **`GCT555_Server/`**: The Python server application.
- **`GCT555_Client/`**: The Unity client project.

---

## Server Setup (Python)

The server utilizes Python and MediaPipe to process video feeds and extract landmarks.

### 1. Environment Setup

It is recommended to use Conda for managing the environment.

1.  Open your terminal or command prompt.
2.  Create a new Conda environment named `gct555`:
    ```bash
    conda create -n gct555 python=3.10
    ```
3.  Activate the environment:
    ```bash
    conda activate gct555
    ```

### 2. Install Dependencies

Navigate to the `GCT555_Server` directory and install the required packages:

```bash
cd GCT555_Server
pip install -r requirements.txt
```

### 3. Download Models

The server requires specific MediaPipe models to function. A script is provided to download these models automatically.

-   **Windows**: Run the `download_model.bat` file located in the `GCT555_Server` directory.

This will create a `models/` directory and download:
-   `pose_landmarker_heavy.task`
-   `hand_landmarker.task`
-   `face_landmarker.task`

*> **Note**: The `models/` directory is excluded from version control.*

### 4. Running the Server

You can run the server for different tracking modes based on your needs. Ensure your environment is active (`conda activate gct555`).

-   **Pose Tracking**:
    ```bash
    python server_pose.py
    ```
-   **Hand Tracking**:
    ```bash
    python server_hand.py
    ```
-   **Face Tracking**:
    ```bash
    python server_face.py
    ```

---

## Client Setup (Unity)

The client is a Unity application that connects to the Python server.

### 1. Requirements

-   **Unity Version**: `6000.3.latest`
    -   *Tested on: `6000.3.4f1`*

### 2. Opening the Project

1.  Open **Unity Hub**.
2.  Click on the **Add** button and select **Add project from disk**.
3.  Navigate to and select the `GCT555_Client` folder.
4.  Open the project in the specified Unity version.

---

## Folder Overview

### `GCT555_Server/`
-   **`server_*.py`**: Main entry points for different tracking modes (Pose, Hand, Face).
-   **`requirements.txt`**: Python dependencies list.
-   **`download_model.bat`**: Script to download necessary MediaPipe models.
-   **`models/`**: (Generated) Directory storing downloaded model files.
-   **`UnityScripts/`**: Contains C# scripts corresponding to the logic used in the Unity client.

### `GCT555_Client/`
-   Standard Unity project structure.
-   **`Assets/`**: Contains all game assets, scenes, and scripts.
-   **`ProjectSettings/`**: Configuration files for the Unity project.

---

## .gitignore

A unified `.gitignore` file is provided at the root of the repository to handle both Python and Unity specific exclusions, as well as the server's `models/` directory.
