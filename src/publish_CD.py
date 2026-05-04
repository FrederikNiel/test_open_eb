#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publish CD frames as ROS2 Image messages (rmw_zenoh_cpp handles transport).
"""

import argparse
import signal
import sys

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image

from metavision_core.event_io import EventsIterator, LiveReplayEventsIterator, is_live_camera
from metavision_sdk_core import PeriodicFrameGenerationAlgorithm, ColorPalette


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Publish CD frames as ROS2 Image messages.",
		formatter_class=argparse.ArgumentDefaultsHelpFormatter,
	)
	parser.add_argument(
		"-i",
		"--input-event-file",
		dest="event_file_path",
		default="",
		help=(
			"Path to input event file (RAW, DAT, HDF5). If not specified, the camera live stream is used. "
			"If it's a camera serial number, it will try to open that camera instead."
		),
	)
	parser.add_argument("--topic", default="/openeb/cd/image", help="ROS2 Image topic name.")
	parser.add_argument("--frame-id", default="openeb_cd", help="Frame id for the Image header.")
	parser.add_argument("--fps", type=int, default=25, help="CD frame publish rate.")
	parser.add_argument(
		"--accumulation-time-us",
		type=int,
		default=10000,
		help="Event accumulation time in microseconds.",
	)
	parser.add_argument(
		"--delta-t-us",
		type=int,
		default=1000,
		help="EventsIterator batching delta in microseconds.",
	)
	parser.add_argument(
		"--max-frames",
		type=int,
		default=0,
		help="Stop after publishing this many frames (0 = no limit).",
	)
	return parser.parse_args()


def _frame_to_msg(node: Node, frame: np.ndarray, frame_id: str) -> Image:
	if not frame.flags["C_CONTIGUOUS"]:
		frame = np.ascontiguousarray(frame)
	if frame.dtype != np.uint8:
		frame = frame.astype(np.uint8, copy=False)

	msg = Image()
	msg.header.stamp = node.get_clock().now().to_msg()
	msg.header.frame_id = frame_id

	if frame.ndim == 2:
		msg.height, msg.width = frame.shape
		msg.encoding = "mono8"
		msg.is_bigendian = False
		msg.step = msg.width
		msg.data = frame.tobytes()
		return msg

	if frame.ndim == 3 and frame.shape[2] == 3:
		msg.height, msg.width, _ = frame.shape
		msg.encoding = "bgr8"
		msg.is_bigendian = False
		msg.step = msg.width * 3
		msg.data = frame.tobytes()
		return msg

	raise ValueError(f"Unsupported frame shape: {frame.shape}")


def main() -> int:
	args = parse_args()

	rclpy.init()

	qos = QoSProfile(depth=5)
	qos.reliability = ReliabilityPolicy.BEST_EFFORT
	qos.history = HistoryPolicy.KEEP_LAST

	node = Node("openeb_cd_publisher")
	publisher = node.create_publisher(Image, args.topic, qos)

	mv_iterator = EventsIterator(input_path=args.event_file_path, delta_t=args.delta_t_us)
	height, width = mv_iterator.get_size()

	if not is_live_camera(args.event_file_path):
		mv_iterator = LiveReplayEventsIterator(mv_iterator)

	event_frame_gen = PeriodicFrameGenerationAlgorithm(
		sensor_width=width,
		sensor_height=height,
		fps=args.fps,
		accumulation_time_us=args.accumulation_time_us,
		palette=ColorPalette.Dark,
	)

	stopping = {"flag": False}

	def _signal_handler(_sig, _frame):
		stopping["flag"] = True

	signal.signal(signal.SIGINT, _signal_handler)
	signal.signal(signal.SIGTERM, _signal_handler)

	published = {"count": 0}

	def on_cd_frame_cb(_ts, cd_frame):
		msg = _frame_to_msg(node, cd_frame, args.frame_id)
		publisher.publish(msg)
		published["count"] += 1

	event_frame_gen.set_output_callback(on_cd_frame_cb)

	for evs in mv_iterator:
		if stopping["flag"] or not rclpy.ok():
			break
		event_frame_gen.process_events(evs)
		rclpy.spin_once(node, timeout_sec=0.0)
		if args.max_frames and published["count"] >= args.max_frames:
			break

	node.destroy_node()
	rclpy.shutdown()
	return 0


if __name__ == "__main__":
	sys.exit(main())
