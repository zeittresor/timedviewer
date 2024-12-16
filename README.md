# timedviewer

View pictures of a folder as long with its subfolders (with the last timestamp) in fullscreen mode.

The Script is looking every x seconds into the choosen folder (and the subfolders of it), if a new
image is available there the current viewed image swaps to the new one.

The "TimedViewer" Script gives u an efficient tool for displaying images with smooth transitions 
that uses resources intelligently and can be flexibly controlled using various command line options. 

For presentations, slideshows, image creation using Stable Diffusion in a batch, Wildlife Cameras OPs
or other applications even where memory efficient image display is required.

Usual if you start the script it waits for images (or show existing images until new images show up)
without the GUI. If you like to see the graphical user interface you can start it using "timedviewer.py -gui".

![timedviewer_config](https://github.com/user-attachments/assets/3866fd80-3c36-4b48-b2da-d312134227cc)

Optional Starfield Effect while waiting for new images is available using Gui Mode.

![grafik](https://github.com/user-attachments/assets/574429ef-6045-4fda-b9aa-8f10b1db4db4)


usage: timedviewer.py [-commandlineoption]

TimedViewer: Image display with transitions and logging.

optional arguments:

  -h, --help         show this help message and exit

  -gui               Start the tool in GUI Mode with additional options
  
  -noprotocol        Ignore the protocol file and display all images.
  
  -allprotocol       Add all existing images in all subdirectories to the
                     protocol file without displaying them. Only newly
                     added images will be displayed in subsequent runs.
                     
  -version           Display version information and exit.

  -noclick           Disable left mousekey to exit the viewer

  -showconsole       Show the console for use with gui mode

Source: https://github.com/zeittresor/timedviewer

Requirements: Make sure you have installed the additional python library
"PyGame" using "pip install pygame". Start it using "py timedviewer.py" using console
or as a shortcut with parameter "timedviewer.py -gui" for the graphical interface mode.
