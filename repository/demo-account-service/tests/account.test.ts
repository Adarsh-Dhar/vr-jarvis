import { deleteAccount } from '../services/account';

jest.mock('../db/users.repo', () => ({ users: { repo: { delete: jest.fn() } } }));

describe('deleteAccount', () => {
  it('deletes own account', async () => {
    await expect(deleteAccount('u1')).resolves.toEqual({ ok: true });
  });
});
