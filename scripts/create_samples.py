"""Create original, synthetic demonstration PDFs (no personal or external data)."""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {
    'distributed-systems-notes.pdf': [
        ('Distributed systems · Study notes', 'A distributed system is a collection of independent computers that work together. Distribution can improve availability and capacity, but introduces network delays and partial failures. A system must account for machines failing independently. These notes are synthetic educational examples for the CiteWise demo.'),
        ('HDFS · Storage and metadata', 'HDFS stores large files as blocks distributed across DataNodes. In this example, the replication factor is three, meaning each block has three copies. The NameNode manages filesystem metadata, including filenames and block locations. DataNodes store block replicas. Replication helps the system tolerate a DataNode failure. The Secondary NameNode creates checkpoints; it is not a hot standby NameNode.'),
        ('Service level agreements', 'A service level agreement defines measurable commitments between a provider and a customer. Availability is often expressed as a percentage of time the service is operational. In this example, the monthly availability target is 99.9 percent. For a 30-day month, the corresponding downtime budget is 43.2 minutes. Service level indicators measure performance; service level objectives specify the targets.'),
        ('Fault tolerance and recovery', 'When a DataNode fails, surviving replicas remain available. The NameNode detects missing heartbeats and schedules new replicas on healthy DataNodes. Recovery time depends on the data volume, available bandwidth, and competing workloads. Replication improves availability but consumes additional storage.'),
    ],
    'gfs-architecture-notes.pdf': [
        ('GFS · Architecture overview', 'The Google File System uses a master and multiple chunkservers. The master manages filesystem metadata, file-to-chunk mapping, and replica locations. Chunkservers store file data as chunks. Clients ask the master for metadata and then communicate with chunkservers for data access. These are synthetic educational notes for the CiteWise demonstration.'),
        ('GFS · Replication and writes', 'GFS uses chunk replication to improve fault tolerance. In this example, each chunk has three replicas. For a write, a primary replica orders mutations and secondary replicas apply them in that order. The master grants leases that determine which replica acts as primary. Replication and checksums help protect stored data.'),
    ],
}


def main():
    target = ROOT / 'samples'
    target.mkdir(exist_ok=True)
    style = ParagraphStyle('body', fontName='Helvetica', fontSize=12, leading=21, textColor=colors.HexColor('#40574b'))
    for name, pages in SAMPLES.items():
        pdf = canvas.Canvas(str(target / name), pagesize=A4)
        pdf.setTitle(name.replace('-', ' ').removesuffix('.pdf'))
        for i, (title, text) in enumerate(pages, 1):
            pdf.setFillColor(colors.HexColor('#174c41'))
            pdf.setFont('Helvetica-Bold', 11)
            pdf.drawString(54, 780, 'CITEWISE / DEMO COLLECTION')
            pdf.setFont('Helvetica-Bold', 21)
            pdf.drawString(54, 720, title)
            paragraph = Paragraph(text, style)
            _, height = paragraph.wrap(480, 600)
            paragraph.drawOn(pdf, 54, 675 - height)
            pdf.setFont('Helvetica', 9)
            pdf.setFillColor(colors.HexColor('#8a9781'))
            pdf.drawString(54, 45, f'Synthetic study notes · Page {i}')
            pdf.showPage()
        pdf.save()
        print(target / name)


if __name__ == '__main__':
    main()
