// Complex TypeScript types for testing

interface User {
  id: number;
  name: string;
  email: string;
}

interface Admin extends User {
  permissions: string[];
}

type UserRole = 'user' | 'admin' | 'moderator';

type Maybe<T> = T | null;

type Result<T, E = Error> = {
  success: true;
  data: T;
} | {
  success: false;
  error: E;
};

interface Repository<T, K> {
  findById(id: K): Maybe<T>;
  save(entity: T): Promise<Result<T>>;
  delete(id: K): Promise<void>;
}

class GenericRepository<T, K> implements Repository<T, K> {
  private data: Map<K, T> = new Map();

  async findById(id: K): Maybe<T> {
    return this.data.get(id) || null;
  }

  async save(entity: T): Promise<Result<T>> {
    const id = (entity as any).id;
    this.data.set(id, entity);
    return { success: true, data: entity };
  }

  async delete(id: K): Promise<void> {
    this.data.delete(id);
  }
}

// Function with generics
function transform<T, U>(data: T[], fn: (item: T) => U): U[] {
  return data.map(fn);
}

// Complex function signature
function fetchWithRetry<T>(
  url: string,
  options: RequestInit = {},
  retries: number = 3
): Promise<Result<T>> {
  return Promise.resolve({ success: true, data: null as any });
}

// Type guards
function isAdmin(user: User): user is Admin {
  return 'permissions' in user;
}

// Union types
type Status = 'pending' | 'in_progress' | 'completed' | 'failed';

interface Task {
  id: number;
  title: string;
  status: Status;
}

// Conditional types
type NonNullable<T> = T extends null | undefined ? never : T;

// Mapped types
type ReadonlyUser = Readonly<User>;

// Template literal types
type EventName<T extends string> = `on${Capitalize<T>}`;

// Recursive types
type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export {
  User,
  Admin,
  UserRole,
  Maybe,
  Result,
  Repository,
  GenericRepository,
  transform,
  fetchWithRetry,
  isAdmin,
  Status,
  Task,
  NonNullable,
  ReadonlyUser,
  EventName,
  JsonValue
};
