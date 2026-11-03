import { users } from '../db/users.repo';

export async function getAccount(id: string) {
  return { id };
}

export async function deleteAccount(id: string) {
  await users.repo.delete(id);
  return { ok: true };
}
