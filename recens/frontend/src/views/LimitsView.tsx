import * as React from "react";
import { Check, X } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, Callout, DataTable } from "@/components/ui/display";
import { api } from "@/lib/api";
import { useActions, useApp } from "@/lib/store";
import { num } from "@/lib/utils";
import type { Plan } from "@/lib/types";
import { PageHeader } from "@/views/shared";

export function LimitsView() {
  const { catalog } = useApp();
  const { run } = useActions();
  const [plans, setPlans] = React.useState<{
    plans: Plan[];
    principle: string;
    free_actions: string[];
  } | null>(null);

  React.useEffect(() => {
    void run(async () => setPlans(await api.get("/plans")));
  }, [run]);

  return (
    <>
      <PageHeader title="Batas produk">
        Batasan berikut melekat pada produk dan tidak dapat dimatikan.
      </PageHeader>

      <Card className="mb-3.5">
        <CardContent className="pt-5">
          <div className="grid gap-2.5 sm:grid-cols-2">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.06em] text-success">
              <Check className="size-3.5" /> Yang dilakukan Recens
            </div>
            <div className="hidden items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.06em] text-destructive sm:flex">
              <X className="size-3.5" /> Yang tidak dilakukan Recens
            </div>
            {catalog!.product_limits.map((limit) => (
              <React.Fragment key={limit.rule}>
                <div className="rounded-md border border-success/25 bg-success/5 px-3.5 py-2.5 text-[13px]">
                  {limit.does}
                </div>
                <div className="rounded-md border border-destructive/25 bg-destructive/5 px-3.5 py-2.5 text-[13px]">
                  {limit.does_not}
                  <p className="mt-1 font-mono text-[10.5px] text-muted-foreground">
                    {limit.rule}
                  </p>
                </div>
              </React.Fragment>
            ))}
          </div>
        </CardContent>
      </Card>

      {plans ? (
        <Card>
          <CardHeader>
            <CardTitle>Paket akses</CardTitle>
          </CardHeader>
          <CardContent>
            <Callout className="mb-3.5">{plans.principle}</Callout>
            <DataTable
              columns={["Paket", "Cocok untuk", "Kuota", "Durasi", "Akses fitur"]}
              rows={plans.plans.map((plan) => [
                <span key="n" className="font-semibold">
                  {plan.label}
                </span>,
                plan.suitable_for,
                `${num(plan.credits)} kredit${
                  plan.project_limit ? `, ${plan.project_limit} proyek` : ", proyek tak terbatas"
                }`,
                plan.duration_days ? `${plan.duration_days} hari` : "—",
                plan.feature_access,
              ])}
            />
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              <span className="text-[11.5px] text-muted-foreground">
                Berjalan lokal tanpa menagih kredit:
              </span>
              {plans.free_actions.map((action) => (
                <Badge key={action}>{action}</Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </>
  );
}
