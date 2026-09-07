function KnowledgeBase() {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<{pct: string | number, msg: string} | null>(null);

  useEffect(() => {
    fetchDocuments().then(res => {
      setDocs(res.source_documents || []);
      setLoading(false);
    }).catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, []);

  const handleUpload = async (e) => {
    if (!e.target.files?.length) return;
    setUploading(true);
    setProgress({ pct: 0, msg: "Starting upload..." });
    try {
      await ingest(e.target.files, (pct, msg) => {
        setProgress({ pct, msg });
      }, null);
      const res = await fetchDocuments();
      setDocs(res.source_documents || []);
    } catch (err) {
      alert("Upload failed: " + err.message);
    } finally {
      setUploading(false);
      setProgress(null);
      e.target.value = null;
    }
  };

  const handleDelete = async (doc) => {
