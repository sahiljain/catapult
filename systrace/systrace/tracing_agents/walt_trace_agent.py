# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import py_utils
import optparse

from devil.android import device_utils
from systrace import trace_result
from systrace import tracing_agents
from py_trace_event import trace_time as trace_time_module

TRACE_FILE_PATH = \
    '/sdcard/Android/data/org.chromium.latency.walt/files/trace.txt'

def try_create_agent(options):
  if options.walt:
    return WaltTraceAgent()
  return None


class WaltTraceConfig(tracing_agents.TracingConfig):
  def __init__(self, device_serial_number, walt):
    tracing_agents.TracingConfig.__init__(self)
    self.device_serial_number = device_serial_number
    self.walt = walt

def add_options(parser):
  options = optparse.OptionGroup(parser, 'WALT trace options')
  options.add_option('--walt', dest='walt', default=False,
                    action='store_true', help='Use the WALT tracing agent.')
  return options

def get_config(options):
  return WaltTraceConfig(options.device_serial_number, options.walt)


class WaltTraceAgent(tracing_agents.TracingAgent):
  def __init__(self):
    super(WaltTraceAgent, self).__init__()
    self._trace_data = False
    self._config = None
    self._device_utils = None
    self._clock_sync_time = None
    self._clock_sync_id = None

  def __repr__(self):
    return 'WaltTrace'

  @py_utils.Timeout(tracing_agents.START_STOP_TIMEOUT)
  def StartAgentTracing(self, config, timeout=None):
    # pylint: disable=unused-argument
    self._config = config
    self._device_utils = device_utils.DeviceUtils(
        self._config.device_serial_number, disable_gce=True)
    if self._device_utils.PathExists(TRACE_FILE_PATH):
      # clear old trace events
      self._device_utils.WriteFile(TRACE_FILE_PATH, '')
    return True

  @py_utils.Timeout(tracing_agents.START_STOP_TIMEOUT)
  def StopAgentTracing(self, timeout=None):
    contents = self._device_utils.ReadFile(TRACE_FILE_PATH)
    print contents
    self._trace_data = '# tracer: \n' + contents \
                       + '# clock_type=LINUX_CLOCK_MONOTONIC\n'
    if self._clock_sync_time is not None:
      self._trace_data += '<0>-0  (-----) [001] ...1  ' \
           + str(self._clock_sync_time) \
           + ': tracing_mark_write: trace_event_clock_sync: name=' \
           + self._clock_sync_id + '\n'
    return True

  def SupportsExplicitClockSync(self):
    return True

  def RecordClockSyncMarker(self, sync_id, did_record_clock_sync_callback):
    cmd = 'cat /proc/timer_list | grep now'
    with self._device_utils.adb.PersistentShell(
        self._config.device_serial_number) as shell:
      t1 = trace_time_module.Now()
      nsec = shell.RunCommand(cmd, close=True)[0][1].split()[2]
      self._clock_sync_time = float(nsec) / 1e9
      self._clock_sync_id = sync_id
      did_record_clock_sync_callback(t1, sync_id)

  @py_utils.Timeout(tracing_agents.GET_RESULTS_TIMEOUT)
  def GetResults(self, timeout=None):
    return trace_result.TraceResult('waltTrace', self._trace_data)
