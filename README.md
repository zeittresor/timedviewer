# timedviewer

View pictures of a folder as long with its subfolders (with the last timestamp) in fullscreen mode.

The Script is looking every x seconds into the choosen folder (and the subfolders of it), if a new
image is available there the current viewed image swaps to the new one.

The "TimedViewer" Script gives u an efficient tool for displaying images with smooth transitions 
that uses resources intelligently and can be flexibly controlled using various command line options. 

For presentations, slideshows, image creation using Stable Diffusion in a batch, Wildlife Cameras OPs
or other applications even where memory efficient image display is required.

If you start the script just select the folder what you want to be "observed" (including its subfolders)
by the script and click start. Now any not already viewed image will be viewed. After all already viewed
images are viewed the script will wait until new images are availabe inside any subfolder and view them.

btw. to get some help there are tooltips for every visible function of the GUI. :-)

<img width="646" height="627" alt="grafik" src="https://github.com/user-attachments/assets/5ee632dd-88cf-4710-b281-f561b06700fd" />

usage: timedviewer.py [-commandlineoption]

TimedViewer: Image display with transitions and logging.

optional arguments:

  -h, --help         show this help message and exit

  -nogui             Start the tool without GUI Mode with additional options
  
  -noprotocol        Ignore the protocol file and display all images.
  
  -allprotocol       Add all existing images in all subdirectories to the
                     protocol file without displaying them. Only newly
                     added images will be displayed in subsequent runs.
                     
  -version           Display version information and exit.

  -noclick           Disable left mousekey to exit the viewer

  -showconsole       Show the console for use with gui mode

Source: https://github.com/zeittresor/timedviewer

Requirements: Make sure you have installed the additional python library
"PyGame" using "pip install pygame". Start the script using "py timedviewer.py".

v3.3 (09/2025)
- Added Effects
- More Presets
- Bugfixes

v3.2 (04/2025)
- Changed -25 to -75 in All Protocol Option
- Added Effects

v3.1 (01/2025)
- Added Option for All Protocol (-25)
- Added Yo-Yo Image Loop
- Added ignore transition effect (for loop)
- Added Presets for default values and for FUM (FreeU-Move) Extension for Stable Diffusion Forge WebUI
  (FreeU-Move Extension is available here https://github.com/zeittresor/sd-forge-fum)

v3.0 (12/2024)
- Commandline version changed to GUI Version by default
