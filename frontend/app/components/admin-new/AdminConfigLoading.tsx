export function AdminConfigLoading() {
  return (
    <div className="space-y-3 w-full max-w-xl">
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-40 bg-surface-container animate-pulse rounded-2xl" />
      ))}
    </div>
  );
}
