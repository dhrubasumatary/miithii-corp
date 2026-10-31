"use client";

import { RefreshCw, UserPlus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { TableSkeleton } from "@/components/data-states";
import { AppShell } from "@/components/app-shell";
import { KeyGate } from "@/components/key-gate";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { relativeTime } from "@/lib/format";
import { engine } from "@/lib/engine";
import type { TeamMember } from "@/lib/engine";

export default function TeamPage() {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setMembers(await engine.listUsers());
    } catch {
      toast.error("Could not load the team.");
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function invite() {
    if (!inviteEmail.trim()) return;
    setBusy(true);
    try {
      const created = await engine.inviteUser(inviteEmail.trim());
      toast.success(`Invited ${created.email} — they sign in with this email.`);
      setInviteEmail("");
      await refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Invite failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyGate>
      <AppShell>
        <div className="mx-auto flex max-w-3xl flex-col gap-6">
          <div>
            <h1 className="text-lg font-semibold">Team</h1>
            <p className="text-muted-foreground text-sm">
              Named people, not a shared key. Invited teammates sign in with
              their email — first login activates the seat.
            </p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Invite a teammate</CardTitle>
              <CardDescription>Free plan: 3 named seats.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="invite-email">Work email</Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="invite-email"
                    type="email"
                    value={inviteEmail}
                    onChange={(event) => setInviteEmail(event.target.value)}
                    placeholder="teammate@company.com"
                    disabled={busy}
                  />
                  <Button
                    onClick={() => void invite()}
                    disabled={busy || !inviteEmail.trim()}
                  >
                    <UserPlus className="h-4 w-4" />
                    Invite
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Seats</CardTitle>
                <Button variant="outline" size="sm" onClick={() => void refresh()}>
                  <RefreshCw className="h-4 w-4" />
                  Refresh
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {!loaded ? (
                <TableSkeleton />
              ) : members.length === 0 ? (
                <p className="text-muted-foreground py-8 text-center text-sm">
                  No seats yet — invite your first teammate above.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Email</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead className="text-right">Joined</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {members.map((member) => (
                      <TableRow key={member.id}>
                        <TableCell className="font-medium">{member.email}</TableCell>
                        <TableCell>
                          <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-xs">
                            {member.role}
                          </span>
                        </TableCell>
                        <TableCell className="text-muted-foreground text-right text-xs">
                          {relativeTime(member.joined)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      </AppShell>
    </KeyGate>
  );
}
