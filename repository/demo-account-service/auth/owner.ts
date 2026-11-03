// Returns true when the signed-in user owns the account.
export function checkOwner(userId: string, accountId: string): boolean {
  return userId === accountId;
}
