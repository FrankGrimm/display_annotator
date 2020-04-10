# display_annotate

Python 3 + pygame display annotator, works in Ubuntu 16 with X11.

Note: This project is not actively maintained, designed for pretty specific needs, and mostly here to serve as an inspiration / starting point for people looking to implement their own.

## install

1. Clone the repository, create a virtual environment for it.
2. Install dependencies with `pip -r requirements.txt`
3. Make sure the command line utility `xrandr` is available for multi display setups.

## start

```bash
# fullscreen
python3 annotator.py

# specify which display you want to annotate (for multi display setups)
python3 annotator.py --target "hdmi-1"
```

