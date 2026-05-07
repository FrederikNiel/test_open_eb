#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publish CD frames as ROS2 Image messages (rmw_zenoh_cpp handles transport).
"""

import argparse
import os
import signal
import subprocess
import sys
from typing import List

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image

from metavision_sdk_core import PeriodicFrameGenerationAlgorithm, ColorPalette


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Publish CD frames as ROS2 Image messages.",
		formatter_class=argparse.ArgumentDefaultsHelpFormatter,
	)
	parser.add_argument("--topic", default="/openeb/cd/image", help="ROS2 Image topic base name.")
	parser.add_argument("--topics", default="", help="Comma-separated ROS2 Image topics for multi-camera mode.")
	parser.add_argument("--frame-id", default="openeb_cd", help="Frame id base for the Image header.")
	parser.add_argument("--frame-ids", default="", help="Comma-separated frame ids for multi-camera mode.")
	parser.add_argument(
		"--serials",
		default="",
		help="Comma-separated camera serials for multi-camera mode.",
	)
	parser.add_argument(
		"--auto-detect",
		action="store_true",
		help="Auto-detect connected cameras and use the first --num-cameras of them.",
	)
	parser.add_argument(
		"--num-cameras",
		type=int,
		default=2,
		help="Number of cameras to use with --auto-detect.",
	)
	parser.add_argument("--fps", type=int, default=25, help="CD frame publish rate.")
	parser.add_argument(
		"--accumulation-time-us",
		type=int,
		default=10000,
		help="Event accumulation time in microseconds.",
	)
	parser.add_argument(
		"--max-frames",
		type=int,
		default=0,
		help="Stop after publishing this many frames (0 = no limit).",
	)
	return parser.parse_args()


def _split_csv(value: str) -> List[str]:
	if not value:
		return []
	return [item.strip() for item in value.split(",") if item.strip()]


def _extract_serials(sources) -> List[str]:
	serials: List[str] = []
	for src in sources:
		if isinstance(src, str):
			serials.append(src)
			continue
		if isinstance(src, dict):
			for key in ("source", "path", "serial", "device_serial", "serial_number", "id"):
				value = src.get(key)
				if value:
					serials.append(str(value))
					break
			continue
		for attr in ("source", "path", "serial", "device_serial", "serial_number", "id"):
			if hasattr(src, attr):
				value = getattr(src, attr)
				if callable(value):
					try:
						value = value()
					except Exception:
						value = None
				if value:
					serials.append(str(value))
					break
	return serials


def _open_device(source: str):
	from metavision_hal import DeviceDiscovery

	base = source or ""
	candidates = [base]
	if base and ":" not in base:
		candidates.extend(
			[
				f"serial:{base}",
				f"serial_number:{base}",
				f"device_serial:{base}",
				f"id:{base}",
			]
		)

	for candidate in candidates:
		try:
			device = DeviceDiscovery.open(candidate)
		except Exception:
			device = None
		if device is not None:
			return device, candidate

	return None, candidates


def _auto_detect_serials(num_cameras: int) -> List[str]:
	try:
		from metavision_hal import DeviceDiscovery
	except Exception:
		return []

	sources = []
	for method_name in ("list_available_sources", "list_available", "list_available_devices"):
		if hasattr(DeviceDiscovery, method_name):
			try:
				sources = getattr(DeviceDiscovery, method_name)()
			except Exception:
				sources = []
			if sources:
				break

	serials = _extract_serials(sources)
	return serials[: max(0, num_cameras)]


def _resolve_topics(base_topic: str, topics_csv: str, count: int) -> List[str]:
	topics = _split_csv(topics_csv)
	if topics:
		if len(topics) != count:
			raise ValueError("--topics count must match number of cameras")
		return topics
	if count == 1:
		return [base_topic]
	return [f"{base_topic}_{idx}" for idx in range(count)]


def _resolve_frame_ids(base_frame_id: str, frame_ids_csv: str, count: int) -> List[str]:
	frame_ids = _split_csv(frame_ids_csv)
	if frame_ids:
		if len(frame_ids) != count:
			raise ValueError("--frame-ids count must match number of cameras")
		return frame_ids
	if count == 1:
		return [base_frame_id]
	return [f"{base_frame_id}_{idx}" for idx in range(count)]


def _make_node_name(source_id: str) -> str:
	safe_id = "".join(ch if ch.isalnum() else "_" for ch in source_id)
	if not safe_id:
		return "openeb_cd_publisher"
	return f"openeb_cd_publisher_{safe_id}"


def _spawn_children(
	args: argparse.Namespace,
	serials: List[str],
	topics: List[str],
	frame_ids: List[str],
) -> int:
	script_path = os.path.abspath(__file__)
	processes = []
	for idx, serial in enumerate(serials):
		cmd = [
			sys.executable,
			script_path,
			"--serials",
			serial,
			"--topic",
			topics[idx],
			"--frame-id",
			frame_ids[idx],
			"--fps",
			str(args.fps),
			"--accumulation-time-us",
			str(args.accumulation_time_us),
		]
		if args.max_frames:
			cmd += ["--max-frames", str(args.max_frames)]
		processes.append(subprocess.Popen(cmd))

	def _signal_handler(_sig, _frame):
		for proc in processes:
			if proc.poll() is None:
				proc.terminate()

	signal.signal(signal.SIGINT, _signal_handler)
	signal.signal(signal.SIGTERM, _signal_handler)

	exit_code = 0
	for proc in processes:
		code = proc.wait()
		if code != 0:
			exit_code = 1

	return exit_code


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

def _run_camera_loop(
	node: Node,
	publisher: "rclpy.publisher.Publisher",
	input_path: str,
	frame_id: str,
	args: argparse.Namespace,
	stop_flag: dict,
	errors: List[BaseException],
) -> None:
	try:
		def on_cd_frame_cb(_ts, cd_frame):
			if stop_flag["flag"]:
				return
			msg = _frame_to_msg(node, cd_frame, frame_id)
			publisher.publish(msg)
			published["count"] += 1
			if args.max_frames and published["count"] >= args.max_frames:
				stop_flag["flag"] = True

		published = {"count": 0}

		device, tried = _open_device(input_path)
		if device is None:
			tried_list = ", ".join(tried) if isinstance(tried, list) else str(tried)
			raise RuntimeError(
				f"Failed to open camera {input_path or '<auto>'} (tried: {tried_list})"
			)

		i_cd_decoder = device.get_i_event_cd_decoder()
		i_eventsstreamdecoder = device.get_i_events_stream_decoder()
		i_eventsstream = device.get_i_events_stream()
		if not (i_cd_decoder and i_eventsstreamdecoder and i_eventsstream):
			raise RuntimeError("Missing HAL facilities for live camera")

		event_frame_gen = PeriodicFrameGenerationAlgorithm(
			sensor_width=device.get_i_geometry().get_width(),
			sensor_height=device.get_i_geometry().get_height(),
			fps=args.fps,
			accumulation_time_us=args.accumulation_time_us,
			palette=ColorPalette.Dark,
		)
		event_frame_gen.set_output_callback(on_cd_frame_cb)

		def on_cd_events(event_buffer):
			if stop_flag["flag"]:
				return
			event_frame_gen.process_events(event_buffer)

		i_cd_decoder.add_event_buffer_callback(on_cd_events)
		i_eventsstream.start()
		try:
			while not stop_flag["flag"] and rclpy.ok():
				ret = i_eventsstream.wait_next_buffer()
				if ret < 0:
					break
				raw_data = i_eventsstream.get_latest_raw_data()
				while i_eventsstream.poll_buffer() > 0:
					raw_data = i_eventsstream.get_latest_raw_data()
				if raw_data is not None:
					i_eventsstreamdecoder.decode(raw_data)
		finally:
			i_eventsstream.stop()
		return

	except BaseException as exc:
		errors.append(exc)
		stop_flag["flag"] = True


def main() -> int:
	args = parse_args()

	if not args.serials and not args.auto_detect:
		args.auto_detect = True

	serials = _split_csv(args.serials)
	if args.auto_detect and serials:
		raise ValueError("--auto-detect cannot be combined with --serials")

	if args.auto_detect:
		serials = _auto_detect_serials(args.num_cameras)
		if len(serials) < args.num_cameras:
			raise RuntimeError(
				f"Auto-detect found {len(serials)} cameras, expected {args.num_cameras}"
			)

	if not serials:
		raise RuntimeError("No cameras detected. Use --serials or --auto-detect")

	input_paths = serials

	topics = _resolve_topics(args.topic, args.topics, len(input_paths))
	frame_ids = _resolve_frame_ids(args.frame_id, args.frame_ids, len(input_paths))
	if len(input_paths) > 1:
		return _spawn_children(args, input_paths, topics, frame_ids)

	rclpy.init()

	qos = QoSProfile(depth=1)
	qos.reliability = ReliabilityPolicy.BEST_EFFORT
	qos.history = HistoryPolicy.KEEP_LAST

	node = Node(_make_node_name(input_paths[0]))
	stop_flag = {"flag": False}
	errors: List[BaseException] = []

	def _signal_handler(_sig, _frame):
		stop_flag["flag"] = True

	signal.signal(signal.SIGINT, _signal_handler)
	signal.signal(signal.SIGTERM, _signal_handler)

	publisher = node.create_publisher(Image, topics[0], qos)
	try:
		_run_camera_loop(
			node,
			publisher,
			input_paths[0],
			frame_ids[0],
			args,
			stop_flag,
			errors,
		)
	finally:
		node.destroy_node()
		rclpy.shutdown()

	if errors:
		print(f"Error: {errors[0]}", file=sys.stderr)
		return 1

	return 0


if __name__ == "__main__":
	sys.exit(main())
