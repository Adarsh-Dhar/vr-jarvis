interface User {
    name: string;
    age: number;
}

function processData(user: User): number {
    return user.age * 2;
}

async function fetchFromBackend(): Promise<string> {
    const response = await fetch('/api/data');
    return response.json();
}
