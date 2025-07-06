"""Test suite for Unraid-specific process detector implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

from mover_status.core.process.detector import ProcessDetector
from mover_status.core.process.models import ProcessStatus
from mover_status.core.process.unraid_detector import UnraidMoverDetector

if TYPE_CHECKING:
    from unittest.mock import MagicMock


# Create proper exception classes for mocking
class MockNoSuchProcess(Exception):
    """Mock exception for psutil.NoSuchProcess."""
    pid: int

    def __init__(self, pid: int = 0) -> None:
        self.pid = pid
        super().__init__(f"process no longer exists (pid={pid})")


class MockAccessDenied(Exception):
    """Mock exception for psutil.AccessDenied."""
    pid: int

    def __init__(self, pid: int = 0) -> None:
        self.pid = pid
        super().__init__(f"access denied (pid={pid})")


class MockZombieProcess(Exception):
    """Mock exception for psutil.ZombieProcess."""
    pid: int

    def __init__(self, pid: int = 0) -> None:
        self.pid = pid
        super().__init__(f"zombie process (pid={pid})")


class TestUnraidMoverDetector:
    """Test the Unraid-specific process detector."""

    def _setup_mock_psutil(self, mock_psutil: MagicMock) -> None:
        """Set up mock psutil with proper exception classes."""
        mock_psutil.NoSuchProcess = MockNoSuchProcess
        mock_psutil.AccessDenied = MockAccessDenied
        mock_psutil.ZombieProcess = MockZombieProcess

    def test_unraid_detector_is_process_detector(self) -> None:
        """Test that UnraidMoverDetector is a ProcessDetector."""
        detector = UnraidMoverDetector()
        assert isinstance(detector, ProcessDetector)

    def test_unraid_detector_has_mover_patterns(self) -> None:
        """Test that UnraidMoverDetector has correct mover patterns."""
        detector = UnraidMoverDetector()
        
        # Check that mover patterns are defined
        assert hasattr(detector, 'MOVER_PATTERNS')
        assert 'mover' in detector.MOVER_PATTERNS
        assert '/usr/local/sbin/mover' in detector.MOVER_PATTERNS

    @patch('mover_status.core.process.unraid_detector.psutil')
    def test_detect_mover_with_matching_process(self, mock_psutil: MagicMock) -> None:
        """Test detect_mover when mover process is running."""
        self._setup_mock_psutil(mock_psutil)

        # Mock process data
        mock_proc = Mock()
        mock_proc.info = {
            'pid': 1234,
            'name': 'mover',
            'cmdline': ['/usr/local/sbin/mover']
        }

        # Mock psutil.Process methods
        mock_proc.pid = 1234
        mock_proc.name.return_value = 'mover'
        mock_proc.cmdline.return_value = ['/usr/local/sbin/mover']
        mock_proc.create_time.return_value = 1735728000.0
        mock_proc.status.return_value = 'running'
        mock_proc.cpu_percent.return_value = 15.5
        mock_proc.memory_info.return_value = Mock(rss=1024 * 1024 * 50)  # 50MB
        mock_proc.cwd.return_value = '/tmp'
        mock_proc.username.return_value = 'root'

        # Mock psutil.process_iter to return our mock process
        mock_psutil.process_iter.return_value = [mock_proc]

        detector = UnraidMoverDetector()
        result = detector.detect_mover()

        assert result is not None
        assert result.pid == 1234
        assert result.name == 'mover'
        assert result.command == '/usr/local/sbin/mover'
        assert result.status == ProcessStatus.RUNNING
        assert result.cpu_percent == 15.5
        assert result.memory_mb == 50.0
        assert result.user == 'root'
        assert result.working_directory == '/tmp'

    @patch('mover_status.core.process.unraid_detector.psutil')
    def test_detect_mover_with_no_matching_process(self, mock_psutil: MagicMock) -> None:
        """Test detect_mover when no mover process is running."""
        # Mock process data for non-mover process
        mock_proc = Mock()
        mock_proc.info = {
            'pid': 5678,
            'name': 'bash',
            'cmdline': ['/bin/bash']
        }
        
        # Mock psutil.process_iter to return non-mover process
        mock_psutil.process_iter.return_value = [mock_proc]
        
        detector = UnraidMoverDetector()
        result = detector.detect_mover()
        
        assert result is None

    @patch('mover_status.core.process.unraid_detector.psutil')
    def test_detect_mover_with_multiple_processes(self, mock_psutil: MagicMock) -> None:
        """Test detect_mover with multiple processes, only one is mover."""
        # Mock non-mover process
        mock_proc1 = Mock()
        mock_proc1.info = {
            'pid': 1111,
            'name': 'bash',
            'cmdline': ['/bin/bash']
        }
        
        # Mock mover process
        mock_proc2 = Mock()
        mock_proc2.info = {
            'pid': 2222,
            'name': 'mover',
            'cmdline': ['/usr/local/sbin/mover']
        }
        mock_proc2.pid = 2222
        mock_proc2.name.return_value = 'mover'
        mock_proc2.cmdline.return_value = ['/usr/local/sbin/mover']
        mock_proc2.create_time.return_value = 1735728001.0
        mock_proc2.status.return_value = 'running'
        mock_proc2.cpu_percent.return_value = 0.0
        mock_proc2.memory_info.return_value = Mock(rss=1024 * 1024 * 10)  # 10MB
        mock_proc2.cwd.return_value = '/tmp'
        mock_proc2.username.return_value = 'root'
        
        # Mock psutil.process_iter to return both processes
        mock_psutil.process_iter.return_value = [mock_proc1, mock_proc2]
        
        detector = UnraidMoverDetector()
        result = detector.detect_mover()
        
        assert result is not None
        assert result.pid == 2222
        assert result.name == 'mover'

    @patch('mover_status.core.process.unraid_detector.psutil')
    def test_detect_mover_with_access_denied(self, mock_psutil: MagicMock) -> None:
        """Test detect_mover handles AccessDenied exception."""
        # Mock process that raises AccessDenied
        mock_proc = Mock()
        mock_proc.info = {
            'pid': 3333,
            'name': 'mover',
            'cmdline': ['/usr/local/sbin/mover']
        }
        mock_proc.pid = 3333
        mock_proc.name.return_value = 'mover'
        mock_proc.cmdline.return_value = ['/usr/local/sbin/mover']
        mock_proc.create_time.side_effect = mock_psutil.AccessDenied()
        
        # Mock psutil.process_iter to return process with AccessDenied
        mock_psutil.process_iter.return_value = [mock_proc]
        
        detector = UnraidMoverDetector()
        result = detector.detect_mover()
        
        # Should return None and not crash
        assert result is None

    @patch('mover_status.core.process.unraid_detector.psutil')
    def test_detect_mover_with_no_such_process(self, mock_psutil: MagicMock) -> None:
        """Test detect_mover handles NoSuchProcess exception."""
        # Mock process that raises NoSuchProcess
        mock_proc = Mock()
        mock_proc.info = {
            'pid': 4444,
            'name': 'mover',
            'cmdline': ['/usr/local/sbin/mover']
        }
        mock_proc.pid = 4444
        mock_proc.name.return_value = 'mover'
        mock_proc.cmdline.return_value = ['/usr/local/sbin/mover']
        mock_proc.create_time.side_effect = mock_psutil.NoSuchProcess(4444)
        
        # Mock psutil.process_iter to return process with NoSuchProcess
        mock_psutil.process_iter.return_value = [mock_proc]
        
        detector = UnraidMoverDetector()
        result = detector.detect_mover()
        
        # Should return None and not crash
        assert result is None

    @patch('mover_status.core.process.unraid_detector.psutil')
    def test_is_process_running_with_existing_process(self, mock_psutil: MagicMock) -> None:
        """Test is_process_running with existing process."""
        mock_process = Mock()
        mock_process.is_running.return_value = True
        mock_psutil.Process.return_value = mock_process
        
        detector = UnraidMoverDetector()
        result = detector.is_process_running(1234)
        
        assert result is True
        mock_psutil.Process.assert_called_once_with(1234)

    @patch('mover_status.core.process.unraid_detector.psutil')
    def test_is_process_running_with_non_existing_process(self, mock_psutil: MagicMock) -> None:
        """Test is_process_running with non-existing process."""
        self._setup_mock_psutil(mock_psutil)
        mock_psutil.Process.side_effect = MockNoSuchProcess(9999)

        detector = UnraidMoverDetector()
        result = detector.is_process_running(9999)

        assert result is False

    @patch('mover_status.core.process.unraid_detector.psutil')
    def test_is_process_running_with_access_denied(self, mock_psutil: MagicMock) -> None:
        """Test is_process_running with access denied."""
        self._setup_mock_psutil(mock_psutil)
        mock_psutil.Process.side_effect = MockAccessDenied()

        detector = UnraidMoverDetector()
        result = detector.is_process_running(1234)

        assert result is False

    @patch('mover_status.core.process.unraid_detector.psutil')
    def test_get_process_info_with_existing_process(self, mock_psutil: MagicMock) -> None:
        """Test get_process_info with existing process."""
        mock_process = Mock()
        mock_process.pid = 1234
        mock_process.name.return_value = 'test_process'
        mock_process.cmdline.return_value = ['/bin/test_process', '--arg']
        mock_process.create_time.return_value = 1735728000.0
        mock_process.status.return_value = 'running'
        mock_process.cpu_percent.return_value = 10.5
        mock_process.memory_info.return_value = Mock(rss=1024 * 1024 * 25)  # 25MB
        mock_process.cwd.return_value = '/home/test'
        mock_process.username.return_value = 'testuser'
        
        mock_psutil.Process.return_value = mock_process
        
        detector = UnraidMoverDetector()
        result = detector.get_process_info(1234)
        
        assert result is not None
        assert result.pid == 1234
        assert result.name == 'test_process'
        assert result.command == '/bin/test_process --arg'
        assert result.status == ProcessStatus.RUNNING
        assert result.cpu_percent == 10.5
        assert result.memory_mb == 25.0
        assert result.working_directory == '/home/test'
        assert result.user == 'testuser'

    @patch('mover_status.core.process.unraid_detector.psutil')
    def test_get_process_info_with_non_existing_process(self, mock_psutil: MagicMock) -> None:
        """Test get_process_info with non-existing process."""
        self._setup_mock_psutil(mock_psutil)
        mock_psutil.Process.side_effect = MockNoSuchProcess(9999)

        detector = UnraidMoverDetector()
        result = detector.get_process_info(9999)

        assert result is None

    @patch('mover_status.core.process.unraid_detector.psutil')
    def test_list_processes(self, mock_psutil: MagicMock) -> None:
        """Test list_processes functionality."""
        self._setup_mock_psutil(mock_psutil)

        # Mock process data
        mock_proc1 = Mock()
        mock_proc1.info = {
            'pid': 1111,
            'name': 'process1',
            'cmdline': ['/bin/process1'],
            'create_time': 1735728000.0,
            'status': 'running',
            'username': 'user1',
            'cwd': '/tmp'
        }
        mock_proc1.create_time.return_value = 1735728000.0
        mock_proc1.cpu_percent.return_value = 5.0
        mock_proc1.memory_info.return_value = Mock(rss=1024 * 1024 * 10)  # 10MB
        mock_proc1.pid = 1111
        mock_proc1.name.return_value = 'process1'
        mock_proc1.cmdline.return_value = ['/bin/process1']
        mock_proc1.status.return_value = 'running'
        mock_proc1.cwd.return_value = '/tmp'
        mock_proc1.username.return_value = 'user1'

        mock_proc2 = Mock()
        mock_proc2.info = {
            'pid': 2222,
            'name': 'process2',
            'cmdline': ['/bin/process2'],
            'create_time': 1735728001.0,
            'status': 'running',
            'username': 'user2',
            'cwd': '/home'
        }
        mock_proc2.create_time.return_value = 1735728001.0
        mock_proc2.cpu_percent.return_value = 8.0
        mock_proc2.memory_info.return_value = Mock(rss=1024 * 1024 * 20)  # 20MB
        mock_proc2.pid = 2222
        mock_proc2.name.return_value = 'process2'
        mock_proc2.cmdline.return_value = ['/bin/process2']
        mock_proc2.status.return_value = 'running'
        mock_proc2.cwd.return_value = '/home'
        mock_proc2.username.return_value = 'user2'

        mock_psutil.process_iter.return_value = [mock_proc1, mock_proc2]

        detector = UnraidMoverDetector()
        result = detector.list_processes()

        assert len(result) == 2
        assert result[0].pid == 1111
        assert result[0].name == 'process1'
        assert result[1].pid == 2222
        assert result[1].name == 'process2'

    @patch('mover_status.core.process.unraid_detector.psutil')
    def test_find_processes_with_pattern(self, mock_psutil: MagicMock) -> None:
        """Test find_processes with pattern matching."""
        self._setup_mock_psutil(mock_psutil)

        # Mock process data
        mock_proc1 = Mock()
        mock_proc1.info = {
            'pid': 1111,
            'name': 'test_process',
            'cmdline': ['/bin/test_process'],
            'create_time': 1735728000.0,
            'status': 'running',
            'username': 'user1',
            'cwd': '/tmp'
        }
        mock_proc1.create_time.return_value = 1735728000.0
        mock_proc1.cpu_percent.return_value = 5.0
        mock_proc1.memory_info.return_value = Mock(rss=1024 * 1024 * 10)  # 10MB
        mock_proc1.pid = 1111
        mock_proc1.name.return_value = 'test_process'
        mock_proc1.cmdline.return_value = ['/bin/test_process']
        mock_proc1.status.return_value = 'running'
        mock_proc1.cwd.return_value = '/tmp'
        mock_proc1.username.return_value = 'user1'

        mock_proc2 = Mock()
        mock_proc2.info = {
            'pid': 2222,
            'name': 'other_process',
            'cmdline': ['/bin/other_process'],
            'create_time': 1735728001.0,
            'status': 'running',
            'username': 'user2',
            'cwd': '/home'
        }
        mock_proc2.create_time.return_value = 1735728001.0
        mock_proc2.cpu_percent.return_value = 8.0
        mock_proc2.memory_info.return_value = Mock(rss=1024 * 1024 * 20)  # 20MB
        mock_proc2.pid = 2222
        mock_proc2.name.return_value = 'other_process'
        mock_proc2.cmdline.return_value = ['/bin/other_process']
        mock_proc2.status.return_value = 'running'
        mock_proc2.cwd.return_value = '/home'
        mock_proc2.username.return_value = 'user2'

        mock_psutil.process_iter.return_value = [mock_proc1, mock_proc2]

        detector = UnraidMoverDetector()
        result = detector.find_processes('test')

        assert len(result) == 1
        assert result[0].pid == 1111
        assert result[0].name == 'test_process'

    @patch('mover_status.core.process.unraid_detector.psutil')
    def test_find_processes_no_matches(self, mock_psutil: MagicMock) -> None:
        """Test find_processes with no matches."""
        self._setup_mock_psutil(mock_psutil)

        # Mock process data
        mock_proc = Mock()
        mock_proc.info = {
            'pid': 1111,
            'name': 'unrelated_process',
            'cmdline': ['/bin/unrelated_process'],
            'create_time': 1735728000.0,
            'status': 'running',
            'username': 'user1',
            'cwd': '/tmp'
        }
        mock_proc.create_time.return_value = 1735728000.0
        mock_proc.cpu_percent.return_value = 5.0
        mock_proc.memory_info.return_value = Mock(rss=1024 * 1024 * 10)  # 10MB
        mock_proc.pid = 1111
        mock_proc.name.return_value = 'unrelated_process'
        mock_proc.cmdline.return_value = ['/bin/unrelated_process']
        mock_proc.status.return_value = 'running'
        mock_proc.cwd.return_value = '/tmp'
        mock_proc.username.return_value = 'user1'

        mock_psutil.process_iter.return_value = [mock_proc]

        detector = UnraidMoverDetector()
        result = detector.find_processes('nonexistent')

        assert len(result) == 0

    @patch('mover_status.core.process.unraid_detector.psutil')
    def test_mover_pattern_matching_variations(self, mock_psutil: MagicMock) -> None:
        """Test various mover pattern matching scenarios."""
        self._setup_mock_psutil(mock_psutil)

        test_cases = [
            # (command, should_match)
            ('/usr/local/sbin/mover', True),
            ('/usr/local/sbin/mover --dry-run', True),
            ('mover', True),
            ('mover-backup', True),
            ('python /script/mover.py', True),
            ('/bin/bash', False),
            ('/usr/bin/rsync', False),
            ('systemctl start mover', True),
        ]

        for command, should_match in test_cases:
            mock_proc = Mock()
            mock_proc.info = {
                'pid': 1234,
                'name': command.split('/')[-1].split()[0],
                'cmdline': command.split(),
                'create_time': 1735728000.0,
                'status': 'running',
                'username': 'root',
                'cwd': '/tmp'
            }
            mock_proc.create_time.return_value = 1735728000.0
            mock_proc.cpu_percent.return_value = 0.0
            mock_proc.memory_info.return_value = Mock(rss=1024 * 1024 * 10)  # 10MB
            mock_proc.pid = 1234
            mock_proc.name.return_value = command.split('/')[-1].split()[0]
            mock_proc.cmdline.return_value = command.split()
            mock_proc.status.return_value = 'running'
            mock_proc.cwd.return_value = '/tmp'
            mock_proc.username.return_value = 'root'

            mock_psutil.process_iter.return_value = [mock_proc]

            detector = UnraidMoverDetector()
            result = detector.detect_mover()

            if should_match:
                assert result is not None, f"Expected command '{command}' to match but it didn't"
            else:
                assert result is None, f"Expected command '{command}' to not match but it did"

    def test_detector_constants(self) -> None:
        """Test that detector constants are properly defined."""
        detector = UnraidMoverDetector()
        
        assert hasattr(detector, 'MOVER_PATTERNS')
        assert isinstance(detector.MOVER_PATTERNS, list)
        assert len(detector.MOVER_PATTERNS) > 0
        assert all(isinstance(pattern, str) for pattern in detector.MOVER_PATTERNS)