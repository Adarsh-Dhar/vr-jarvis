import { requireAuth } from '../auth/requireAuth';
import { deleteAccount } from '../services/account';

type Route = (req: any, res: any) => Promise<void>;
const routes: Record<string, { middleware: unknown; handler: Route }> = {};

routes['DELETE /account/:id'] = {
  middleware: requireAuth,
  handler: async (req, res) => {
    await deleteAccount(req.params.id);
    res.sendStatus(204);
  },
};

export { routes };
