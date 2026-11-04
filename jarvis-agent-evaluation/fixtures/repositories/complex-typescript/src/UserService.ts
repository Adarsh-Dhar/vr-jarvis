/**
 * Complex TypeScript service with dependency injection
 * Demonstrates advanced typing, generics, and class patterns
 */

interface User {
  id: number;
  username: string;
  email: string;
  roles: Role[];
}

enum Role {
  ADMIN = 'admin',
  USER = 'user',
  MODERATOR = 'moderator'
}

interface Repository<T> {
  findById(id: number): Promise<T | null>;
  findAll(): Promise<T[]>;
  save(entity: T): Promise<T>;
  delete(id: number): Promise<boolean>;
}

class UserRepository implements Repository<User> {
  private users: Map<number, User> = new Map();
  private nextId = 1;

  async findById(id: number): Promise<User | null> {
    return this.users.get(id) || null;
  }

  async findAll(): Promise<User[]> {
    return Array.from(this.users.values());
  }

  async save(user: User): Promise<User> {
    if (!user.id) {
      user.id = this.nextId++;
    }
    this.users.set(user.id, user);
    return user;
  }

  async delete(id: number): Promise<boolean> {
    return this.users.delete(id);
  }
}

class CacheService<T> {
  private cache: Map<string, { data: T; timestamp: number }> = new Map();
  private ttl: number;

  constructor(ttl: number = 60000) {
    this.ttl = ttl;
  }

  get(key: string): T | null {
    const cached = this.cache.get(key);
    if (!cached) return null;
    
    if (Date.now() - cached.timestamp > this.ttl) {
      this.cache.delete(key);
      return null;
    }
    
    return cached.data;
  }

  set(key: string, data: T): void {
    this.cache.set(key, { data, timestamp: Date.now() });
  }

  invalidate(key: string): void {
    this.cache.delete(key);
  }

  clear(): void {
    this.cache.clear();
  }
}

class UserService {
  constructor(
    private repository: Repository<User>,
    private cache: CacheService<User>
  ) {}

  async getUser(id: number): Promise<User | null> {
    const cacheKey = `user:${id}`;
    
    // Try cache first
    const cached = this.cache.get(cacheKey);
    if (cached) return cached;

    // Load from repository
    const user = await this.repository.findById(id);
    if (user) {
      this.cache.set(cacheKey, user);
    }
    
    return user;
  }

  async createUser(username: string, email: string, roles: Role[] = [Role.USER]): Promise<User> {
    const user: User = {
      id: 0, // Will be assigned by repository
      username,
      email,
      roles
    };

    const saved = await this.repository.save(user);
    this.cache.set(`user:${saved.id}`, saved);
    
    return saved;
  }

  async deleteUser(id: number): Promise<boolean> {
    const deleted = await this.repository.delete(id);
    if (deleted) {
      this.cache.invalidate(`user:${id}`);
    }
    return deleted;
  }

  async hasRole(userId: number, role: Role): Promise<boolean> {
    const user = await this.getUser(userId);
    return user ? user.roles.includes(role) : false;
  }
}

// Factory function for dependency injection
function createUserService(): UserService {
  const repository = new UserRepository();
  const cache = new CacheService<User>(60000);
  return new UserService(repository, cache);
}

export { User, Role, Repository, UserRepository, CacheService, UserService, createUserService };
