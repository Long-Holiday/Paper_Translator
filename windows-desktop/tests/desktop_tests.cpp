#include "app_paths.h"
#include "paper_repository.h"
#include "reader_widget.h"
#include "translation_controller.h"
#include <QApplication>
#include <QFile>
#include <QLockFile>
#include <QPainter>
#include <QPdfDocument>
#include <QPdfPageNavigator>
#include <QPdfView>
#include <QPdfWriter>
#include <QScrollBar>
#include <QSettings>
#include <QSignalSpy>
#include <QSqlQuery>
#include <QTemporaryDir>
#include <QtTest>

namespace {
QString writePdf(const QString &root,const QString &name="论文.pdf",bool tall=false) {
    const auto path=root+"/"+name;
    QPdfWriter pdf(path); pdf.setTitle("Desktop Test Paper"); pdf.setResolution(72);
    if(tall) pdf.setPageSize(QPageSize(QSizeF(210,420),QPageSize::Millimeter));
    QPainter painter(&pdf); painter.drawText(50,80,"Page one"); pdf.newPage(); painter.drawText(50,80,"Page two"); painter.end();
    return path;
}
void configure(const QString &root) {
    qputenv("PAPER_TRANSLATOR_HOME",root.toUtf8());
    QSettings settings(AppPaths::settingsFile(),QSettings::IniFormat);
    settings.setValue("translation/service","google"); settings.setValue("translation/model",""); settings.sync();
}
void useFixture(TranslationController &controller,const QString &mode) {
    auto python=qEnvironmentVariable("PAPER_TEST_PYTHON");
    if(python.isEmpty()) python=AppPaths::pythonExecutable();
    controller.setEngineCommand(python,{QStringLiteral(PAPER_TEST_SOURCE_DIR)+"/tests/fake_engine.py",mode});
}
}
class DesktopTests : public QObject {
    Q_OBJECT
private slots:
    void repositoryImportsPersistsAndDeletes() {
        QTemporaryDir temp; QVERIFY(temp.isValid()); const auto input=writePdf(temp.path()); qint64 id;
        {
            PaperRepository repo(temp.path()); auto paper=repo.importPdf(input); id=paper.id;
            QCOMPARE(paper.pages,2); QCOMPARE(paper.title,QString("Desktop Test Paper"));
            QVERIFY(QFile::exists(paper.originalPath)); QCOMPARE(repo.list("desktop").size(),1);
            repo.savePosition(id,100); QCOMPARE(repo.get(id).lastPage,2);
            repo.setStatus(id,"translating",60);
        }
        {
            PaperRepository repo(temp.path()); auto paper=repo.get(id);
            QCOMPARE(paper.lastPage,2); QCOMPARE(paper.status,QString("failed"));
            QVERIFY(!paper.error.isEmpty()); repo.remove(id);
            QVERIFY(repo.list().isEmpty()); QVERIFY(!QDir(repo.paperDirectory(id)).exists()); QVERIFY(QFile::exists(input));
        }
    }
    void invalidPdfDoesNotCreateRowsOrFiles() {
        QTemporaryDir temp; QFile invalid(temp.path()+"/invalid.pdf"); QVERIFY(invalid.open(QIODevice::WriteOnly)); invalid.write("not PDF"); invalid.close();
        PaperRepository repo(temp.path()); QVERIFY_EXCEPTION_THROWN(repo.importPdf(invalid.fileName()),std::runtime_error);
        QVERIFY(repo.list().isEmpty());
    }
    void legacyImportCopiesPathsAndReadingPosition() {
        QTemporaryDir source,destination;
        auto input=writePdf(source.path());
        { PaperRepository repo(source.path()); auto paper=repo.importPdf(input); repo.savePosition(paper.id,2); }
        PaperRepository repo(destination.path()); QCOMPARE(repo.importLegacy(source.path()+"/data"),1);
        auto paper=repo.list().first(); QCOMPARE(paper.lastPage,2); QVERIFY(paper.originalPath.startsWith(destination.path()));
        QVERIFY(QFile::exists(paper.originalPath)); QVERIFY(QFile::exists(source.path()+"/data/papers/1/original.pdf"));
        QVERIFY_EXCEPTION_THROWN(repo.importLegacy(source.path()+"/data"),std::runtime_error);
    }
    void legacyMissingFileRollsBack() {
        QTemporaryDir source,destination;
        auto input=writePdf(source.path());
        { PaperRepository repo(source.path()); repo.importPdf(input); auto second=repo.importPdf(input); QFile::remove(second.originalPath); }
        PaperRepository repo(destination.path()); QVERIFY_EXCEPTION_THROWN(repo.importLegacy(source.path()+"/data"),std::runtime_error);
        QVERIFY(repo.list().isEmpty()); QVERIFY(!QDir(repo.paperDirectory(1)).exists());
    }
    void queueProcessesUtf8AndPublishesOnlyOnSuccessfulExit() {
        QTemporaryDir temp; configure(temp.path()); PaperRepository repo(temp.path());
        const auto source=writePdf(temp.path()); auto first=repo.importPdf(source),second=repo.importPdf(source);
        TranslationController controller(repo); useFixture(controller,"success");
        controller.enqueue(first.id); controller.enqueue(first.id); controller.enqueue(second.id);
        QTRY_VERIFY_WITH_TIMEOUT(!controller.busy(),10000);
        for(auto id:{first.id,second.id}) { auto paper=repo.get(id); QCOMPARE(paper.status,QString("completed")); QCOMPARE(paper.progress,100); QVERIFY(QFile::exists(paper.translatedPath)); }
    }
    void engineFailures_data() {
        QTest::addColumn<QString>("mode");
        for(auto mode:{"fail","invalid","missing","wrong-path"}) QTest::newRow(mode)<<QString(mode);
    }
    void engineFailures() {
        QFETCH(QString,mode);
        QTemporaryDir temp; configure(temp.path()); PaperRepository repo(temp.path()); auto paper=repo.importPdf(writePdf(temp.path()));
        TranslationController controller(repo); useFixture(controller,mode); controller.enqueue(paper.id);
        QTRY_VERIFY_WITH_TIMEOUT(!controller.busy(),10000);
        QCOMPARE(repo.get(paper.id).status,QString("failed")); QVERIFY(!repo.get(paper.id).error.isEmpty());
        QCOMPARE(repo.get(paper.id).progress,0);
    }
    void unavailableEngineRecoversQueue() {
        QTemporaryDir temp; configure(temp.path()); PaperRepository repo(temp.path()); auto source=writePdf(temp.path());
        auto first=repo.importPdf(source),second=repo.importPdf(source);
        TranslationController controller(repo); controller.setEngineCommand(temp.path()+"/missing-python",{});
        controller.enqueue(first.id); controller.enqueue(second.id);
        QTRY_VERIFY_WITH_TIMEOUT(!controller.busy(),5000);
        QCOMPARE(repo.get(first.id).status,QString("failed")); QCOMPARE(repo.get(second.id).status,QString("failed"));
    }
    void cancelRunningAndQueuedJobs() {
        QTemporaryDir temp; configure(temp.path()); PaperRepository repo(temp.path()); auto source=writePdf(temp.path());
        auto first=repo.importPdf(source),second=repo.importPdf(source);
        TranslationController controller(repo); useFixture(controller,"hang"); controller.enqueue(first.id); controller.enqueue(second.id);
        QTRY_COMPARE_WITH_TIMEOUT(repo.get(first.id).progress,50,5000);
        controller.cancel(second.id); QCOMPARE(repo.get(second.id).status,QString("failed"));
        controller.cancel(first.id); QTRY_VERIFY_WITH_TIMEOUT(!controller.busy(),5000);
        QCOMPARE(repo.get(first.id).status,QString("failed"));
    }
    void shutdownStopsActiveEngineAndQueue() {
        QTemporaryDir temp; configure(temp.path()); PaperRepository repo(temp.path()); auto source=writePdf(temp.path());
        auto first=repo.importPdf(source),second=repo.importPdf(source);
        TranslationController controller(repo); useFixture(controller,"hang"); controller.enqueue(first.id); controller.enqueue(second.id);
        QTRY_COMPARE_WITH_TIMEOUT(repo.get(first.id).progress,50,5000); controller.shutdown();
        QVERIFY(!controller.busy()); QCOMPARE(repo.get(first.id).status,QString("failed")); QCOMPARE(repo.get(second.id).status,QString("failed"));
    }
    void readerSynchronizesPagesScrollAndReleasesFiles() {
        QTemporaryDir temp; PaperRepository repo(temp.path()); auto paper=repo.importPdf(writePdf(temp.path()));
        const auto translated=writePdf(temp.path(),"tall.pdf",true);
        AppPaths::copyFile(translated,repo.paperDirectory(paper.id)+"/translated.pdf");
        repo.complete(paper.id,repo.paperDirectory(paper.id)+"/translated.pdf"); paper=repo.get(paper.id); paper.lastPage=2;
        ReaderWidget reader; reader.resize(1000,700); reader.show(); reader.openPaper(paper);
        auto left=reader.findChild<QPdfView *>("originalView"),right=reader.findChild<QPdfView *>("translatedView");
        QVERIFY(left); QVERIFY(right); QCOMPARE(reader.currentPage(),2);
        QCOMPARE(left->pageNavigator()->currentPage(),1); QCOMPARE(right->pageNavigator()->currentPage(),1);
        QSignalSpy saved(&reader,&ReaderWidget::positionChanged); reader.setPage(1); QCOMPARE(saved.count(),1);
        for(auto view:{left,right}) { view->setZoomMode(QPdfView::ZoomMode::Custom); view->setZoomFactor(2); }
        QTRY_VERIFY(left->verticalScrollBar()->maximum()>0);
        QVERIFY(right->verticalScrollBar()->maximum()!=left->verticalScrollBar()->maximum());
        left->verticalScrollBar()->setValue(left->verticalScrollBar()->maximum()/2);
        QTRY_VERIFY(qAbs(right->verticalScrollBar()->value()-right->verticalScrollBar()->maximum()/2)<=2);
        reader.releaseTranslation(paper.id); QCOMPARE(right->document()->pageCount(),0);
        reader.clear(); QCOMPARE(left->document()->pageCount(),0); QCOMPARE(reader.paperId(),qint64(0));
    }
    void nativeStartupAndSingleInstanceLock() {
        QTemporaryDir temp; configure(temp.path());
        auto path=QCoreApplication::applicationDirPath()+"/PaperTranslator";
#ifdef Q_OS_WIN
        path+=".exe";
#endif
        QProcess process; process.start(path,{"--smoke-test"}); QVERIFY(process.waitForFinished(10000));
        QCOMPARE(process.exitCode(),0);
        QLockFile lock(temp.path()+"/desktop.lock"); QVERIFY(lock.tryLock());
        process.start(path,{"--smoke-test"}); QVERIFY(process.waitForFinished(10000)); QCOMPARE(process.exitCode(),1);
    }
};
QTEST_MAIN(DesktopTests)
#include "desktop_tests.moc"
