#!/usr/bin/env python
"""
A script for making a new tar package and Homebrew formula.
Also uploads the generated .tar.gz file to S3 if you provide --upload flag.

usage: package-osx.py [-h] [--upload] version

Run it with the same folder as kd.go. It will output 2 files to the same
directory:

    kd-1.0.0.tar.gz  # packaged "kd" binary
    kd.rb            # Homebrew formula

The formula can be installed with after the formula file is created:

    brew install kd.rb

"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

import boto
from boto.s3.key import Key


AWS_KEY = 'AKIAJSUVKX6PD254UGAA'
AWS_SECRET = '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'

FORMULA = """\
require 'formula'

class Kd < Formula
  homepage 'http://koding.com'
  # url and sha1 needs to be changed after new binary is uploaded.
  url '{url}'
  sha1 '{sha1}'

  def install
    bin.install "kd"
  end
end
"""


def main():
    parser = argparse.ArgumentParser(
        description="Compile kd tool and upload to S3.")
    parser.add_argument('version')
    parser.add_argument('--upload', action='store_true', help="upload to s3")
    args = parser.parse_args()

    tarname = "kd-%s.tar.gz" % args.version

    workdir = tempfile.mkdtemp()
    try:
        tardir = os.path.join(workdir, "kd")  # dir to be tarred
        os.mkdir(tardir)

        print "Building kd tool..."
        binpath = os.path.join(tardir, "kd")
        cmd = "go build -o %s %s" % (binpath, "kd.go")
        try:
            subprocess.check_call(cmd.split())
        except:
            print "Cannot compile kd tool. Try manually."
            sys.exit(1)

        print "Making tar file..."
        tarpath = os.path.join(workdir, tarname)
        cwd = os.getcwd()
        os.chdir(workdir)
        with tarfile.open(tarpath, "w:gz") as tar:
            tar.add("kd")
        os.chdir(cwd)

        # Move the tar to current working directory
        dst = os.path.join(cwd, tarname)
        shutil.move(tarpath, dst)
        tarpath = dst

        # Upload to Amazon S3
        if args.upload:
            print "Uploading to Amazon S3..."
            c = boto.connect_s3(AWS_KEY, AWS_SECRET)
            b = c.get_bucket('kd-tool')
            k = Key(b)
            k.key = tarname
            if k.exists():
                print "This version is already uploaded. " \
                      "Please do not overwrite the uploaded version, " \
                      "increment the version number and upload it again."
                sys.exit(1)

            k.set_contents_from_filename(tarpath)
            k.make_public()
            url = k.generate_url(expires_in=0, query_auth=False)
        else:
            # For testing "brew install" locally
            url = "http://127.0.0.1:8000/kd-%s.tar.gz" % args.version

        print "Generating formula..."
        sha1 = sha1_file(tarpath)
        formula_str = FORMULA.format(url=url, sha1=sha1)
        with open("kd.rb", "w") as f:
            f.write(formula_str)

        print "Done. Generated files:"
        print "    %s" % tarname
        print "    kd.rb"

        if not args.upload:
            print "Did not upload to S3. " \
                  "If you want to upload, run with --upload flag."

    finally:
        shutil.rmtree(workdir)


def sha1_file(path):
    """Calculate sha1 of path. Read file in chunks."""
    assert os.path.isfile(path)
    chunk_size = 1024 ** 3
    sha1_checksum = hashlib.sha1()
    with open(path, "rb") as f:
        byte = f.read(chunk_size)
        while byte:
            sha1_checksum.update(byte)
            byte = f.read(chunk_size)
    return sha1_checksum.hexdigest()


if __name__ == "__main__":
    main()
