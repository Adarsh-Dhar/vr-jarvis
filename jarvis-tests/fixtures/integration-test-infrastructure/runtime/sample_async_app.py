#!/usr/bin/env python3
"""
Sample async application for runtime tracing
Tests async execution, threading, and concurrent operations
"""

import asyncio
import time
from typing import List, Dict


async def fetch_data(url: str, delay: float = 0.1) -> Dict:
    """Simulate async data fetch"""
    await asyncio.sleep(delay)
    return {
        'url': url,
        'data': f"Data from {url}",
        'timestamp': time.time()
    }


async def process_data(data: Dict) -> Dict:
    """Process data asynchronously"""
    await asyncio.sleep(0.05)
    return {
        'processed': True,
        'original': data,
        'result': data['data'].upper()
    }


async def main_flow(urls: List[str]) -> List[Dict]:
    """Main async flow: fetch and process multiple URLs"""
    # Fetch all data concurrently
    fetch_tasks = [fetch_data(url) for url in urls]
    fetched_data = await asyncio.gather(*fetch_tasks)

    # Process all data concurrently
    process_tasks = [process_data(data) for data in fetched_data]
    processed_data = await asyncio.gather(*process_tasks)

    return processed_data


async def sequential_flow(urls: List[str]) -> List[Dict]:
    """Sequential async flow"""
    results = []
    for url in urls:
        data = await fetch_data(url)
        processed = await process_data(data)
        results.append(processed)
    return results


class AsyncWorker:
    """Async worker class"""

    def __init__(self, name: str):
        self.name = name
        self.tasks_completed = 0

    async def work(self, task: str) -> str:
        """Perform work asynchronously"""
        await asyncio.sleep(0.1)
        self.tasks_completed += 1
        return f"{self.name} completed: {task}"


async def worker_pool(workers: List[AsyncWorker], tasks: List[str]) -> List[str]:
    """Run tasks through worker pool"""
    worker_tasks = []
    for i, task in enumerate(tasks):
        worker = workers[i % len(workers)]
        worker_tasks.append(worker.work(task))

    return await asyncio.gather(*worker_tasks)


async def main():
    """Main async application"""
    print("Starting async sample application...")

    urls = [
        "https://api.example.com/data1",
        "https://api.example.com/data2",
        "https://api.example.com/data3"
    ]

    # Concurrent flow
    print("\nConcurrent flow:")
    start = time.time()
    concurrent_results = await main_flow(urls)
    print(f"Concurrent time: {time.time() - start:.2f}s")
    print(f"Results: {len(concurrent_results)} items")

    # Sequential flow
    print("\nSequential flow:")
    start = time.time()
    sequential_results = await sequential_flow(urls)
    print(f"Sequential time: {time.time() - start:.2f}s")
    print(f"Results: {len(sequential_results)} items")

    # Worker pool
    print("\nWorker pool:")
    workers = [AsyncWorker(f"Worker{i}") for i in range(2)]
    tasks = [f"Task{i}" for i in range(4)]
    worker_results = await worker_pool(workers, tasks)
    print(f"Worker results: {worker_results}")

    print("\nAsync application completed.")


if __name__ == "__main__":
    asyncio.run(main())
