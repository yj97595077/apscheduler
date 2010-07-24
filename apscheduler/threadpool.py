"""
Generic thread pool class. Modeled after Java's ThreadPoolExecutor.
"""

from Queue import Queue, Empty
from threading import Thread, Lock
import logging


logger = logging.getLogger(__name__)

class ThreadPool(object):
    def __init__(self, core_threads=0, max_threads=None, keepalive=1,
                 exception_callback=None):
        """
        :param core_threads: maximum number of persistent threads in the pool
        :param max_threads: maximum number of total threads in the pool
        :param thread_class: callable that creates a Thread object
        :param keepalive: seconds to keep non-core worker threads waiting
            for new tasks
        :param exception_callback: callable to call when task execution raises
            an exception
        """
        self.queue = Queue()
        self.threads_lock = Lock()
        self.num_threads = 0
        self.busy_threads = 0
        self.core_threads = core_threads
        self.max_threads = max_threads
        self.keepalive = keepalive
        self.exception_callback = exception_callback

        if max_threads:
            self.max_threads = max(max_threads, core_threads, 1)

        logger.info('Started thread pool with %d core threads and %s maximum '
                    'threads', core_threads, max_threads or 'unlimited')

    def _add_thread(self):
        core = self.num_threads < self.core_threads
        t = Thread(target=self._run_jobs, args=(core,))
        t.setDaemon(True)
        t.start()

    def _add_threadcount(self, increment):
        self.threads_lock.acquire()
        self.num_threads += increment
        self.threads_lock.release()

    def _add_busycount(self, increment):
        self.threads_lock.acquire()
        self.busy_threads += increment
        self.threads_lock.release()

    def _run_jobs(self, core):
        logger.debug('Started worker thread')
        self._add_threadcount(1)

        block = True
        timeout = None
        if not core:
            block = self.keepalive > 0
            timeout = self.keepalive

        while True:
            try:
                func, args, kwargs = self.queue.get(block, timeout)
            except Empty:
                break

            self._add_busycount(1)
            try:
                func(*args, **kwargs)
            except:
                logger.exception('Exception occurred when running task')
                if self.exception_callback:
                    self.exception_callback()
            self._add_busycount(-1)

        self._add_threadcount(-1)
        logger.debug('Exiting worker thread')

    def execute(self, func, args=(), kwargs={}):
        self.threads_lock.acquire()
        try:
            if (self.busy_threads == self.num_threads and not
                self.max_threads or self.num_threads < self.max_threads):
                self._add_thread()
        finally:
            self.threads_lock.release()

        self.queue.put((func, args, kwargs))
