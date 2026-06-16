import { Card, CardContent } from "@/components/ui/card";

export function PagePlaceholder({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      <Card>
        <CardContent className="flex min-h-64 flex-col items-center justify-center gap-1 text-center">
          <p className="text-sm font-medium">Nothing here yet</p>
          <p className="text-sm text-muted-foreground">
            This is a placeholder. Build out the {title.toLowerCase()} view here.
          </p>
        </CardContent>
      </Card>
    </>
  );
}
