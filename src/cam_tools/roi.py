#!/usr/bin/python3
# -*- coding: utf-8 -*-

def get_roi_from_file(path: str):
    """
    Helper function to read bias from a file
    """
    roi = {}
    try:
        roi_file = open(path, 'r')
    except IOError:
        print("Cannot open roi file: " + path)
    else:
        for line in roi_file:

            # Skip lines starting with '%': comments
            if line.startswith('%'):
                continue

            split_line = line.split(" ")
            if len(split_line) == 4:
                roi['x'] = int(split_line[0])
                roi['y'] = int(split_line[1])
                roi['width'] = int(split_line[2])
                roi['height'] = int(split_line[3])

    return roi


def save_roi_to_file(path: str, roi: dict):
    """
    helper function to write biases to file
    """
    if 'x' in roi and 'y' in roi and 'width' in roi and 'height' in roi:
        try:
            roi_file = open(path, 'w')
        except IOError:
            print("Cannot save roi file to: " + path)
        else:
            roi_file.write("{0} {1} {2} {3}".format(roi['x'],
                                                    roi['y'],
                                                    roi['width'],
                                                    roi['height']))
