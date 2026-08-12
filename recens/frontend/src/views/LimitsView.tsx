import * as React from "react";
import { Check, X } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle, Section } from "@/components/ui/card";
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

      <Section>
        <div className="grid gap-x-8 gap-y-0 sm:grid-cols-2">
          <p className="flex items-center gap-1.5 border-b border-border pb-2 text-[12.5px] font-semibold text-success">
            <Check className="size-3.5" /> Yang dilakukan Recens
          </p>
          <p className="hidden items-center gap-1.5 border-b border-border pb-2 text-[12.5px] font-semibold text-destructive sm:flex">
            <X className="size-3.5" /> Yang tidak dilakukan Recens
          </p>
          {catalog!.product_limits.map((limit) => (
            <React.Fragment key={limit.rule}>
              <p className="border-b border-border py-3 text-[13px] leading-relaxed">
                {limit.does}
              </p>
              <p className="border-b border-border py-3 text-[13px] leading-relaxed text-muted-foreground">
                {limit.does_not}
                <span className="mt-0.5 block font-mono text-[10.5px] text-faint">
                  {limit.rule}
                </span>
              </p>
            </React.Fragment>
          ))}
        </div>
      </Section>

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
