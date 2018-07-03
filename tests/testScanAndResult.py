from __future__ import print_function


import time
import unittest
import xml.etree.ElementTree as ET

from ospd.ospd import OSPDaemon, OSPDError

class Result(object):
    def __init__(self, type_, **kwargs):
        self.result_type=type_
        self.host=''
        self.name=''
        self.value=''
        self.port=''
        self.test_id=''
        self.severity=''
        self.qod=''
        for name, value in kwargs.items():
            setattr(self, name, value)

class DummyWrapper(OSPDaemon):
    def __init__(self, results, checkresult=True):
        OSPDaemon.__init__(self, 'cert', 'key', 'ca')
        self.checkresult = checkresult
        self.results = results

    def check(self):
        return self.checkresults

    def get_custom_vt_as_xml_str(self, custom):
        return '<mytest>static test</mytest>'

    def exec_scan(self, scan_id, target):
        time.sleep(0.01)
        for res in self.results:
            if res.result_type=='log':
                self.add_scan_log(scan_id, res.host or target, res.name, res.value, res.port)
            if res.result_type == 'error':
                self.add_scan_error(scan_id, res.host or target, res.name, res.value, res.port)
            elif res.result_type == 'host-detail':
                self.add_scan_error(scan_id, res.host  or target, res.name, res.value)
            elif res.result_type == 'alarm':
                self.add_scan_alarm(scan_id, res.host or target, res.name, res.value, res.port, res.test_id, res.severity, res.qod)
            else:
                raise ValueError(res.result_type)

class FullTest(unittest.TestCase):
    # TODO: There should be a lot more assert in there !

    def testGetDefaultScannerParams(self):
        daemon = DummyWrapper([])
        response = ET.fromstring(daemon.handle_command('<get_scanner_details />'))
        # The status of the response must be success (i.e. 200)
        self.assertEqual(response.get('status'), '200')
        # The response root element must have the correct name
        self.assertEqual(response.tag, 'get_scanner_details_response')
        # The response must contain a 'scanner_params' element
        self.assertIsNotNone(response.find('scanner_params'))

    def testGetDefaultHelp(self):
        daemon = DummyWrapper([])
        response = ET.fromstring(daemon.handle_command('<help />'))
        print(ET.tostring(response))
        response = ET.fromstring(daemon.handle_command('<help format="xml" />'))
        print(ET.tostring(response))

    def testGetDefaultScannerVersion(self):
        daemon = DummyWrapper([])
        response = ET.fromstring(daemon.handle_command('<get_version />'))
        print(ET.tostring(response))

    def testGetVTs_no_VT(self):
        daemon = DummyWrapper([])
        response = ET.fromstring(daemon.handle_command('<get_vts />'))
        print(ET.tostring(response))

    def testGetVTs_single_VT(self):
        daemon = DummyWrapper([])
        daemon.add_vt('1.2.3.4', 'A vulnerability test')
        response = ET.fromstring(daemon.handle_command('<get_vts />'))
        print(ET.tostring(response))

    def testGetVTs_multiple_VTs(self):
        daemon = DummyWrapper([])
        daemon.add_vt('1.2.3.4', 'A vulnerability test')
        daemon.add_vt('some id', 'Another vulnerability test')
        daemon.add_vt('123456789', 'Yet another vulnerability test')
        response = ET.fromstring(daemon.handle_command('<get_vts />'))
        print(ET.tostring(response))

    def testGetVTs_multiple_VTs_with_custom(self):
        daemon = DummyWrapper([])
        daemon.add_vt('1.2.3.4', 'A vulnerability test')
        daemon.add_vt('some id', 'Another vulnerability test with custom info', { 'depencency': '1.2.3.4' })
        daemon.add_vt('123456789', 'Yet another vulnerability test')
        response = ET.fromstring(daemon.handle_command('<get_vts />'))
        print(ET.tostring(response))

    def testiScanWithError(self):
        daemon = DummyWrapper([
            Result('error', value='something went wrong'),
        ])

        response = ET.fromstring(daemon.handle_command('<start_scan target="localhost" ports="80, 443"><scanner_params /></start_scan>'))
        print(ET.tostring(response))
        scan_id = response.findtext('id')
        finished = False
        while not finished:
            response = ET.fromstring(daemon.handle_command('<get_scans scan_id="%s" details="0"/>' % scan_id))
            print(ET.tostring(response))
            scans = response.findall('scan')
            self.assertEqual(1, len(scans))
            scan = scans[0]
            if int(scan.get('progress')) != 100:
                self.assertEqual('0', scan.get('end_time'))
                time.sleep(.010)
            else:
                finished = True
        response = ET.fromstring(daemon.handle_command('<get_scans scan_id="%s"/>' % scan_id))
        print(ET.tostring(response))
        response = ET.fromstring(daemon.handle_command('<get_scans />'))
        print(ET.tostring(response))
        response = ET.fromstring(daemon.handle_command('<get_scans scan_id="%s" details="1"/>' % scan_id))
        self.assertEqual(response.findtext('scan/results/result'), 'something went wrong')
        print(ET.tostring(response))

        response = ET.fromstring(daemon.handle_command('<delete_scan scan_id="%s" />' % scan_id))
        self.assertEqual(response.get('status'), '200')
        print(ET.tostring(response))

    def testStopScan(self):
        daemon = DummyWrapper([])
        response = ET.fromstring(
            daemon.handle_command('<start_scan ' +
                                  'target="localhost" ports="80, 443">' +
                                  '<scanner_params /></start_scan>'))
        print(ET.tostring(response))
        scan_id = response.findtext('id')
        time.sleep(0.01)

        response = daemon.stop_scan(scan_id)
        self.assertEqual(response, None)

        response = ET.fromstring(daemon.handle_command(
            '<stop_scan scan_id="%s" />' % scan_id))
        self.assertEqual(response.get('status'), '200')
        print(ET.tostring(response))

    def testScanWithVTs(self):
        daemon = DummyWrapper([])
        cmd = ET.fromstring('<start_scan ' +
                                  'target="localhost" ports="80, 443">' +
                                  '<scanner_params /><vts /></start_scan>')
        print(ET.tostring(cmd))
        self.assertRaises(OSPDError, daemon.handle_start_scan_command, cmd)

        response = ET.fromstring(
            daemon.handle_command('<start_scan ' +
                                  'target="localhost" ports="80, 443">' +
                                  '<scanner_params /><vts>1.2.3.4</vts></start_scan>'))
        print(ET.tostring(response))
        scan_id = response.findtext('id')
        time.sleep(0.01)
        self.assertEqual(daemon.get_scan_vts(scan_id), '1.2.3.4')
        self.assertNotEqual(daemon.get_scan_vts(scan_id), '1.2.3.6')

        response = ET.fromstring(
            daemon.handle_command('<start_scan ' +
                                  'target="localhost" ports="80, 443">' +
                                  '<scanner_params /></start_scan>'))
        print(ET.tostring(response))
        scan_id = response.findtext('id')
        time.sleep(0.01)
        self.assertEqual(daemon.get_scan_vts(scan_id), '')
