// Main application logic

import { User, Admin, UserRole, transform, isAdmin, Task, Status } from './types';

// Simple function
function greet(name: string): string {
  return `Hello, ${name}!`;
}

// Function with type parameters
function createUser(name: string, email: string, role: UserRole = 'user'): User {
  return {
    id: Date.now(),
    name,
    email
  };
}

// Function with complex logic
function processTask(task: Task): Task {
  if (task.status === 'pending') {
    return { ...task, status: 'in_progress' };
  } else if (task.status === 'in_progress') {
    return { ...task, status: 'completed' };
  }
  return task;
}

// Function calling other functions
function handleNewUser(name: string, email: string): User {
  const user = createUser(name, email);
  console.log(greet(user.name));
  return user;
}

// Async function
async function fetchUserData(id: number): Promise<User | null> {
  // Simulate API call
  return null;
}

// Function with error handling
function divide(a: number, b: number): number {
  if (b === 0) {
    throw new Error('Division by zero');
  }
  return a / b;
}

// Class with methods
class UserService {
  private users: Map<number, User> = new Map();

  addUser(user: User): void {
    this.users.set(user.id, user);
  }

  getUser(id: number): User | undefined {
    return this.users.get(id);
  }

  hasAdmin(): boolean {
    for (const user of this.users.values()) {
      if (isAdmin(user)) {
        return true;
      }
    }
    return false;
  }
}

// Higher-order function
function withLogging<T>(fn: (...args: any[]) => T): (...args: any[]) => T {
  return (...args: any[]) => {
    console.log(`Calling ${fn.name} with`, args);
    const result = fn(...args);
    console.log(`Result:`, result);
    return result;
  };
}

// Curried function
const add = (a: number) => (b: number) => a + b;

// Recursive function
function factorial(n: number): number {
  if (n <= 1) return 1;
  return n * factorial(n - 1);
}

// Function with default parameters
function configure(
  port: number = 3000,
  host: string = 'localhost',
  ssl: boolean = false
): void {
  console.log(`Configuring server on ${host}:${port}, SSL: ${ssl}`);
}

// Export for testing
export {
  greet,
  createUser,
  processTask,
  handleNewUser,
  fetchUserData,
  divide,
  UserService,
  withLogging,
  add,
  factorial,
  configure
};
