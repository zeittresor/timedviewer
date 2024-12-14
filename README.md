# timedviewer

View pictures of a folder as long with its subfolders (with the last timestamp) in fullscreen mode.


The "TimedViewer" Script gives u an efficient tool for displaying images with smooth transitions 
that uses resources intelligently and can be flexibly controlled using various command line options. 

For presentations, slideshows, image creation using Stable Diffusion in a batch, Wildlife Cameras OPs
or other applications even where memory efficient image display is required.

Newly added "-gui" Mode:

![timedviewer_config](https://github.com/user-attachments/assets/1c4aa2f2-4b3f-4ee8-a203-0a195c66f2bf)


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
