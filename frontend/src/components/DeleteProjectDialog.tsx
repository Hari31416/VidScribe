import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Trash2, AlertTriangle, Loader2 } from "lucide-react";
import { api, endpoints } from "@/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

interface DeleteProjectDialogProps {
  videoId: string;
}

export function DeleteProjectDialog({ videoId }: DeleteProjectDialogProps) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const deleteStorageMutation = useMutation({
    mutationFn: async () => {
      const res = await api.delete(endpoints.uploads.deleteStorage(videoId));
      return res.data;
    },
    onSuccess: () => {
      setOpen(false);
      // Invalidate project query to update status (e.g. video_exists: false)
      queryClient.invalidateQueries({ queryKey: ["project", videoId] });
      queryClient.invalidateQueries({ queryKey: ["uploads"] });
    },
  });

  const deleteProjectMutation = useMutation({
    mutationFn: async () => {
      const res = await api.delete(endpoints.uploads.deleteProject(videoId));
      return res.data;
    },
    onSuccess: () => {
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["uploads"] });
      // Redirect to dashboard since project is gone
      navigate("/");
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="destructive" className="gap-2">
            <Trash2 className="w-4 h-4" /> Delete
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Delete Project</DialogTitle>
          <DialogDescription>
            Choose how you want to delete artifacts for project <span className="font-mono text-foreground">{videoId}</span>.
          </DialogDescription>
        </DialogHeader>
        
        <div className="grid gap-4 py-4">
            <div className="flex flex-col gap-2 p-4 border rounded-md border-orange-200 bg-orange-50 dark:bg-orange-950/20 dark:border-orange-900">
                <div className="flex items-center gap-2 font-medium text-orange-800 dark:text-orange-300">
                    <AlertTriangle className="w-4 h-4" /> Storage Saver
                </div>
                <p className="text-sm text-muted-foreground">
                    Delete large video and image files only. Keeps transcript and generated notes.
                </p>
                <Button 
                    variant="outline" 
                    className="mt-2 border-orange-300 hover:bg-orange-100 dark:border-orange-800 dark:hover:bg-orange-900/50"
                    onClick={() => deleteStorageMutation.mutate()}
                    disabled={deleteStorageMutation.isPending || deleteProjectMutation.isPending}
                >
                    {deleteStorageMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin mr-2"/> : null}
                    Delete Video & Images Only
                </Button>
            </div>

            <div className="flex flex-col gap-2 p-4 border rounded-md border-red-200 bg-red-50 dark:bg-red-950/20 dark:border-red-900">
                <div className="flex items-center gap-2 font-medium text-red-800 dark:text-red-300">
                    <Trash2 className="w-4 h-4" /> Delete Everything
                </div>
                <p className="text-sm text-muted-foreground">
                    Permanently remove the entire project, including transcript and notes.
                </p>
                <Button 
                    variant="destructive" 
                    className="mt-2"
                    onClick={() => deleteProjectMutation.mutate()}
                    disabled={deleteStorageMutation.isPending || deleteProjectMutation.isPending}
                >
                    {deleteProjectMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin mr-2"/> : null}
                    Delete Everything
                </Button>
            </div>
        </div>
        
        <DialogFooter>
             <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
