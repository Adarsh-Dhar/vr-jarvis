"""
Async Code Example
Demonstrates async/await patterns with concurrent operations.
"""

import asyncio
from typing import List, Dict
import time


async def fetch_data(url: str) -> Dict[str, any]:
    """Simulate fetching data from a URL"""
    await asyncio.sleep(0.1)  # Simulate network delay
    return {
        'url': url,
        'data': f'data from {url}',
        'timestamp': time.time()
    }


async def process_data(data: Dict[str, any]) -> Dict[str, any]:
    """Process fetched data"""
    await asyncio.sleep(0.05)  # Simulate processing
    return {
        'processed': True,
        'original_data': data,
        'result': f'processed {data["data"]}'
    }


async def fetch_and_process(urls: List[str]) -> List[Dict[str, any]]:
    """Fetch and process data from multiple URLs concurrently"""
    tasks = []

    for url in urls:
        # Fetch data
        fetch_task = asyncio.create_task(fetch_data(url))
        tasks.append(fetch_task)

    # Wait for all fetches to complete
    fetch_results = await asyncio.gather(*tasks)

    # Process results
    process_tasks = []
    for result in fetch_results:
        process_task = asyncio.create_task(process_data(result))
        process_tasks.append(process_task)

    processed_results = await asyncio.gather(*process_tasks)

    return processed_results


async def main():
    """Main async function"""
    urls = [
        'https://api.example.com/data1',
        'https://api.example.com/data2',
        'https://api.example.com/data3'
    ]

    results = await fetch_and_process(urls)

    for result in results:
        print(result)


if __name__ == '__main__':
    asyncio.run(main())
