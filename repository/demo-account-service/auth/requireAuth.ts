import { verifyToken } from '../lib/token';

type Req = { headers: { authorization?: string }; user?: { id: string } };
type Res = { sendStatus(code: number): void };

export function requireAuth(req: Req, res: Res, next: () => void) {
  const user = verifyToken(req.headers.authorization);
  if (!user) return res.sendStatus(401);
  req.user = user;
  next();
}
