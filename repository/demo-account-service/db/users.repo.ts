import { query } from './client';

export async function deleteUser(id: string) {
  await query('DELETE FROM users WHERE id = $1', [id]);
}

export const users = {
  repo: { delete: deleteUser },
};
