import time
import unittest

import numpy as np

from app.services.cluster_manager import ClusterManager, OFFLOADABLE_FILTERS, WorkerInfo
from app.services.edge_worker import AVAILABLE_FILTERS, process_chunk


class EdgeDistributionTests(unittest.IsolatedAsyncioTestCase):
    def test_worker_advertises_only_implemented_filters(self):
        self.assertEqual(set(AVAILABLE_FILTERS), OFFLOADABLE_FILTERS)
        self.assertNotIn("frequency_restoration", AVAILABLE_FILTERS)
        self.assertNotIn("normalize", AVAILABLE_FILTERS)

    async def test_all_chunks_are_processed_and_duration_is_preserved(self):
        manager = ClusterManager()
        worker = WorkerInfo("127.0.0.2")
        worker.status = "online"
        worker.last_seen = time.time()
        worker.available_filters = list(AVAILABLE_FILTERS)
        manager._workers["127.0.0.2:8877"] = worker

        async def local_remote(_worker, chunk, sr, filters, _chunk_id):
            return process_chunk(chunk, sr, filters)

        manager._send_chunk_to_worker = local_remote
        audio = np.linspace(-0.2, 0.2, 32000, dtype=np.float32)
        result = await manager.process_distributed(
            audio, 16000, {"auto_eq": True}
        )

        self.assertEqual(len(result), len(audio))
        self.assertTrue(np.all(np.isfinite(result)))
        self.assertGreater(float(np.max(np.abs(result - audio))), 1e-6)

    def test_unimplemented_filter_is_never_distributed(self):
        manager = ClusterManager()
        worker = WorkerInfo("127.0.0.2")
        worker.status = "online"
        worker.last_seen = time.time()
        worker.available_filters = list(AVAILABLE_FILTERS)
        manager._workers["127.0.0.2:8877"] = worker
        self.assertFalse(manager.can_distribute({"frequency_restoration": True}))


if __name__ == "__main__":
    unittest.main()
